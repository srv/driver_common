#***********************************************************
#* Software License Agreement (BSD License)
#*
#*  Copyright (c) 2008, Willow Garage, Inc.
#*  All rights reserved.
#*
#*  Redistribution and use in source and binary forms, with or without
#*  modification, are permitted provided that the following conditions
#*  are met:
#*
#*   * Redistributions of source code must retain the above copyright
#*     notice, this list of conditions and the following disclaimer.
#*   * Redistributions in binary form must reproduce the above
#*     copyright notice, this list of conditions and the following
#*     disclaimer in the documentation and/or other materials provided
#*     with the distribution.
#*   * Neither the name of the Willow Garage nor the names of its
#*     contributors may be used to endorse or promote products derived
#*     from this software without specific prior written permission.
#*
#*  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#*  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#*  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
#*  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
#*  COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
#*  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
#*  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#*  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#*  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
#*  LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
#*  ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#*  POSSIBILITY OF SUCH DAMAGE.
#***********************************************************

# Author: Blaise Gassend

# Given a set of parameters, generates the messages, service types, and
# classes to allow runtime reconfiguration. Documentation of a node's
# parameters is a handy byproduct.

## @todo
# Need to check types of min max and default
# Need to put sane error on exceptions

import roslib; roslib.load_manifest("dynamic_reconfigure")
import roslib.packages
from string import Template
import os
import inspect
import string 

LINEDEBUG="#line"
#LINEDEBUG="//#line"

# Convenience names for types
str_t = "str"
bool_t = "bool"
int_t = "int"
double_t = "double"

class ParameterGenerator:
    minval = {
            'int' : 'INT_MIN',
            'double' : '-std::numeric_limits<double>::infinity()',
            'str' : '',
            'bool' : False,
            }
            
    maxval = {
            'int' : 'INT_MAX',
            'double' : 'std::numeric_limits<double>::infinity()',
            'str' : '',
            'bool' : True,
            }
    
    defval = {
            'int' : 0,
            'double' : 0,
            'str' : '',
            'bool' : False,
            }
        
    def check_type(self, param, field, default):
        value = param[field]
        # If no value, use default.
        if value == None:
            param[field] = default
            return
        # Check that value type is compatible with type.
        pytype = { 'str':str, 'int':int, 'double':float, 'bool':bool }[param['type']]
        param['ctype'] = { 'str':'std::string', 'int':'int', 'double':'double', 'bool':'bool' }[param['type']]
        if value and pytype != type(value) and (pytype != float or type(value) != int):
            raise TypeError("'%s' has type %s, but default is %s"%(param['name'], param['type'], repr(value)))
        # Do any necessary casting.
        param[field] = pytype(value)
    
    def __init__(self):
        self.parameters = []
        self.dynconfpath = roslib.packages.get_pkg_dir("dynamic_reconfigure")

    def add(self, name, paramtype, level, description, default = None, min = None, max = None, edit_method = ""):
        newparam = {
            'name' : name,
            'type' : paramtype,
            'default' : default,
            'level' : level,
            'description' : description,
            'min' : min,
            'max' : max,
            'srcline' : inspect.currentframe().f_back.f_lineno,
            'srcfile' : inspect.getsourcefile(inspect.currentframe().f_back.f_code),
            'edit_method' : edit_method,
        }
        if type == str_t and (max != None or min != None):
            raise Exception("Max or min specified for %s, which is of string type"%name)

        self.check_type(newparam, 'default', self.defval[paramtype])
        self.check_type(newparam, 'max', self.maxval[paramtype])
        self.check_type(newparam, 'min', self.minval[paramtype])
        self.parameters.append(newparam)

    def mkdirabs(self, path, second_attempt = False):
        if os.path.isdir(path):
            pass
        elif os.path.isfile(path):
            raise OSError("Error creating directory %s, a file with the same name exists" %path)
        elif second_attempt: # An exception occurred, but we still don't know why.
            raise
        else:
            head, tail = os.path.split(path)
            if head and not os.path.isdir(head):
                self.mkdir(head)
            if tail:
                try:
                    os.mkdir(path)
                except OSError:
                    # Probably got created by somebody else, lets check.
                    self.mkdirabs(path, True)

    def mkdir(self, path):
        path = os.path.join(self.pkgpath, path)
        self.mkdirabs(path)

    def generate(self, pkgname, nodename, name):
        try:
            self.pkgname = pkgname
            self.pkgpath = roslib.packages.get_pkg_dir(pkgname)
            self.name = name
            self.nodename = nodename
            self.msgname = name+"Config"
            #print '**************************************************************'
            #print '**************************************************************'
            print Template("Generating reconfiguration files for $name in $pkgname").\
                    substitute(name=self.name, pkgname = self.pkgname)
            #print '**************************************************************'
            #print '**************************************************************'
            self.generatecpp()
            self.generatedoc()
            self.generateusage()
            self.generatepy()
            self.deleteobsolete()
        except Exception, e:
            print "Error building srv %s.srv"%name
            import traceback
            traceback.print_exc()
            exit(1)

    def generatedoc(self):
        self.mkdir("dox")
        f = open(os.path.join(self.pkgpath, "dox", self.msgname+".dox"), 'w')
        #print >> f, "/**"
        print >> f, "\\subsubsection parameters ROS parameters"
        print >> f
        print >> f, "Reads and maintains the following parameters on the ROS server"
        print >> f
        for param in self.parameters:
            print >> f, Template("- \\b \"~$name\" : \\b [$type] $description min: $min, default: $default, max: $max").substitute(param)
        print >> f
        #print >> f, "*/"
        f.close()

    def generateusage(self):
        self.mkdir("dox")
        f = open(os.path.join(self.pkgpath, "dox", self.msgname+"-usage.dox"), 'w')
        #print >> f, "/**"
        print >> f, "\\subsubsection usage Usage"
        print >> f, '\\verbatim'
        print >> f, Template('<node name="$nodename" pkg="$pkgname" type="$nodename">').\
                substitute(pkgname = self.pkgname, nodename = self.nodename)
        for param in self.parameters:
            print >> f, Template('  <param name="$name" type="$type" value="$default" />').substitute(param)
        print >> f, '</node>'
        print >> f, '\\endverbatim'
        print >> f
        #print >> f, "*/"
        f.close()

    def crepr(self, param, val):
        type = param["type"]
        if type == 'str':
            return '"'+val+'"'
        if type in [ 'int', 'double']:
            return str(val)
        if  type == 'bool':
            return { True : 1, False : 0 }[val]
        raise TypeError(type)
#        if type == 'string':
#            return '"'+val+'"'
#        if 'uint' in type:
#            return str(val)+'ULL'
#        if 'int' in type:
#            return str(val)+'LL'
#        if 'time' in type:
#            return 'ros::Time('+str(val)+')'
#        if 'duration' in type:
#            return 'ros::Duration('+str(val)+')'
#        if  'float' in types:
#            return str(val)

    def appendline(self, list, text, param, value = None):
        if value == None:
            val = ""
        else:
            val = self.crepr(param, param[value])
        list.append(Template('${doline} $srcline "$srcfile"\n      '+text).safe_substitute(param, v=val, doline=LINEDEBUG, configname=self.name))
    
    def generatecpp(self):
        # Read the configuration manipulator template and insert line numbers and file name into template.
        templatefile = os.path.join(self.dynconfpath, "templates", "ConfigType.h")
        templatelines = []
        templatefilesafe = templatefile.replace('\\', '\\\\') # line directive does backslash expansion.
        curline = 1
        f = open(templatefile)
        for line in f:
            curline = curline + 1
            templatelines.append(Template(line).safe_substitute(linenum=curline,filename=templatefilesafe))
        f.close()
        template = ''.join(templatelines)
        
        # Write the configuration manipulator.
        cfg_cpp_dir = os.path.join("cfg", "cpp", self.pkgname)
        self.mkdir(cfg_cpp_dir)
        f = open(os.path.join(self.pkgpath, cfg_cpp_dir, self.name+"Config.h"), 'w')
        paramdescr = []
        members = []
        for param in self.parameters:
            self.appendline(members, "${ctype} ${name};", param)
            self.appendline(paramdescr, "__min__.${name} = $v;", param, "min")
            self.appendline(paramdescr, "__max__.${name} = $v;", param, "max")
            self.appendline(paramdescr, "__default__.${name} = $v;", param, "default")
            self.appendline(paramdescr, 
                    "__param_descriptions__.push_back(AbstractParamDescriptionConstPtr(new ParamDescription<${ctype}>(\"${name}\", \"${type}\", ${level}, "\
                    "\"${description}\", \"${edit_method}\", &${configname}Config::${name})));", param)
        paramdescr = string.join(paramdescr, '\n')
        members = string.join(members, '\n')
        f.write(Template(template).substitute(uname=self.name.upper(), configname=self.name,
            pkgname = self.pkgname, paramdescr = paramdescr, members = members, doline = LINEDEBUG))
        f.close()

    def deleteoneobsolete(self, file):
         try:
             os.unlink(file)
         except OSError:
             pass

    def deleteobsolete(self): ### @todo remove this after the transition period.
         self.deleteoneobsolete(os.path.join(self.pkgpath, "msg", self.msgname+".msg"))
         self.deleteoneobsolete(os.path.join("msg", "cpp", self.pkgpath, "msg", self.msgname+".msg"))
         self.deleteoneobsolete(os.path.join(self.pkgpath, "srv", "Get"+self.msgname+".srv"))
         self.deleteoneobsolete(os.path.join("srv", "cpp", self.pkgpath, "srv", "Get"+self.msgname+".srv"))
         self.deleteoneobsolete(os.path.join(self.pkgpath, "srv", "Set"+self.msgname+".srv"))
         self.deleteoneobsolete(os.path.join("srv", "cpp", self.pkgpath, "srv", "Set"+self.msgname+".srv"))

#    def msgtype(self, type):
#        return { 'int' : 'int32', 'bool' : 'int8', 'str' : 'string', 'double' : 'float64' }[type]
#
#    def generatemsg(self):
#        self.mkdir("msg")
#        f = open(os.path.join(self.pkgpath, "msg", self.msgname+".msg"), 'w')
#        print >> f, "# This is an autogerenated file. Please do not edit."
#        print >> f, ""
#        for param in self.parameters:
#            print >> f, Template("$type $name # $description").substitute(param, type=self.msgtype(param['type']))
#        f.close()
#
#    def generategetsrv(self):
#        self.mkdir("srv")
#        f = open(os.path.join(self.pkgpath, "srv", "Get"+self.msgname+".srv"), 'w')
#        print >> f, "# This is an autogerenated file. Please do not edit."
#        print >> f, ""
#        print >> f, "---" 
#        print >> f, self.msgname, "config", "# Current configuration of node."
#        print >> f, self.msgname, "defaults", "# Minimum values where appropriate."
#        print >> f, self.msgname, "min", "# Minimum values where appropriate."
#        print >> f, self.msgname, "max", "# Maximum values where appropriate."
#        f.close()
#
#    def generatesetsrv(self):
#        self.mkdir("srv")
#        f = open(os.path.join(self.pkgpath, "srv", "Set"+self.msgname+".srv"), 'w')
#        print >> f, "# This is an autogerenated file. Please do not edit."
#        print >> f, self.msgname, "config", "# Requested node configuration."
#        print >> f, "---"        
#        print >> f, self.msgname, "config", "# What the node's configuration was actually set to."
#        f.close()
    
    def generatepy(self):
        # Read the configuration manipulator template and insert line numbers and file name into template.
        templatefile = os.path.join(self.dynconfpath, "templates", "ConfigType.py")
        templatelines = []
        f = open(templatefile)
        template = f.read()
        f.close()
        
        # Write the configuration manipulator.
        self.mkdir(os.path.join("src", self.pkgname, "cfg"))
        f = open(os.path.join(self.pkgpath, "src", self.pkgname, "cfg", self.name+"Config.py"), 'w')
        f.write(Template(template).substitute(name = self.name, 
            pkgname = self.pkgname, pycfgdata = self.parameters))
        f.close()

        f = open(os.path.join(self.pkgpath, "src", self.pkgname, "cfg", "__init__.py"), 'a')
        f.close()
