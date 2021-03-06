#!/bin/env python

import argparse
import sys
import os
import yaml
import uhal
#from regmap_helper/tree import * # import node,arraynode,tree
#from tree import * # import node,arraynode,tree
#import regmap_helper/node
sys.path.append("./regmap_helper")
from tree import *

def represent_none(self, _):
    return self.represent_scalar('tag:yaml.org,2002:null', '')

yaml.add_representer(type(None), represent_none)

class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)

#================================================================================
#Generate the MAP and PKG VHDL files for this slave
#================================================================================
def GenerateHDL(name,XMLFile,HDLPath):
  print "Generate HDL for",name,"from",XMLFile
  #get working directory
  wd=os.getcwd()

  #move into the output HDL directory
  os.chdir(wd+"/"+HDLPath)

  #make a symlink to the XML file
  fullXMLFile=wd+"/"+XMLFile

  #generate a fake top address table
  slaveAddress="0x"+hex(0x00000000)[2:]
  topXMLFile="top.xml"

  outXMLFile=open(topXMLFile,'w')
  outXMLFile.write("<?xml version=\"1.0\" encoding=\"ISO-8859-1\"?>\n")
  outXMLFile.write("<node id=\"TOP\">\n")
  outXMLFile.write("  <node id=\"" +name+ "\"        module=\"file://" +fullXMLFile+ "\"        address=\"" +slaveAddress+ "\"/>\n")
  outXMLFile.write("</node>\n")
  outXMLFile.close()
  

  #generate the HDL
  try:
    device = uhal.getDevice("dummy","ipbusudp-1.3://localhost:12345","file://" + topXMLFile)
  except Exception:
    raise Exception("File '%s' does not exist or has incorrect format" % topXMLFile)
  for i in device.getNodes():
    if i.count('.') == 0:
      mytree = tree(device.getNode(i), log)
      mytree.generatePkg()
      mytree.generateRegMap(regMapTemplate=wd+"/regmap_helper/template_map.vhd")
  
  #cleanup
  os.remove(topXMLFile)
  os.chdir(wd)           #go back to original path




#================================================================================
#process a single slave (or tree us sub-slaves) and update all the output files
#================================================================================
#def LoadSlave(slave,tclFile,dtsiFile,addressFile,parentName):
def LoadSlave(name,slave,tclFile,dtsiYAML,aTableYAML,parentName):
  
  fullName=parentName+str(name)
  #update the AddSlaves.tcl file
  if 'TCL_CALL' in slave:
    tclFile.write("#"+fullName+"\n")
    tclFile.write(slave['TCL_CALL']+"\n\n")

  #Build HDL for this file
  if 'HDL' in slave:
    if 'XML' not in slave:
      raise RuntimeError(fullName+" has HDL tag, but no XML tag\n")
    GenerateHDL(fullName,slave['XML'][0],slave['HDL'])

  #generate yaml for the kernel and centos build
  if 'UHAL_BASE' in slave:
    if 'XML' in slave:
      #update list dtsi files to look for (.dtsi_chunk or .dtsi_post_chunk)
      dtsiYAML[fullName]=None
      #update the address table file
      
      aTableYAML[fullName]={
          "UHAL_BASE":"0x"+hex(slave['UHAL_BASE'])[2:].zfill(8),
          "XML":slave['XML']}
      
    else:
      return

  #Handle and additional slaves generated by the TCL command
  if 'SUB_SLAVES' in slave:
    if slave['SUB_SLAVES'] != None:
      for subSlave in slave['SUB_SLAVES']:
        LoadSlave(subSlave,
                  slave['SUB_SLAVES'][subSlave],
                  tclFile,
                  dtsiYAML,
                  aTableYAML,
                  fullName)





def main():
  # configure logger
  global log
  log = logging.getLogger("main")
  formatter = logging.Formatter('%(name)s %(levelname)s: %(message)s')
  handler = logging.StreamHandler(sys.stdout)
  handler.setFormatter(formatter)
  log.addHandler(handler)
  log.setLevel(logging.WARNING)

  #tell uHAL to calm down. 
  uhal.setLogLevelTo(uhal.LogLevel.WARNING)

  #command line
  parser = argparse.ArgumentParser(description="Create auto-generated files for the build system.")
  parser.add_argument("--slavesFile","-s"      ,help="YAML file storing the slave info for generation",required=True)
  parser.add_argument("--addSlaveTCLPath","-t" ,help="Path for AddSlaves.tcl",required=True)
  parser.add_argument("--addressTablePath","-a",help="Path for address table generation yaml",required=True)
  parser.add_argument("--dtsiPath","-d"        ,help="Path for dtsi yaml",required=True)
  args=parser.parse_args()
  
  #AddSlaves tcl file
  tclFile=open(args.addSlaveTCLPath+"/AddSlaves.tcl","w")
  tclFile.write("#================================================================================\n")
  tclFile.write("#  Configure and add AXI slaves\n")
  tclFile.write("#  Auto-generated by \n")
  tclFile.write("#================================================================================\n")
  
  #dtsi yaml file
  dtsiYAMLFile=open(args.dtsiPath+"/slaves.yaml","w")
  dtsiYAML = dict()

  #address table yaml file
  addressTableYAMLFile=open(args.addressTablePath+"/slaves.yaml","w")
  aTableYAML = dict()

  #source slave yaml to drive the rest of the build
  slavesFile=open(args.slavesFile)
  slaves=yaml.load(slavesFile)
  for slave in slaves['AXI_SLAVES']:
    #update all the files for this slave
    LoadSlave(slave,
              slaves["AXI_SLAVES"][slave],
              tclFile,
              dtsiYAML,
              aTableYAML,
              "")

  dtsiYAML={"DTSI_CHUNKS": dtsiYAML}
  aTableYAML={"UHAL_MODULES": aTableYAML}
  
  dtsiYAMLFile.write(yaml.dump(dtsiYAML,
                               Dumper=MyDumper,
                               default_flow_style=False))
  addressTableYAMLFile.write(yaml.dump(aTableYAML,
                                       Dumper=MyDumper,
                                       default_flow_style=False))


if __name__ == "__main__":
    main()
