import os
import sys
import glob
import pickle
from lxml import etree

nsmap = {}
vxbpel_ns = "http://www.turkselma.com/vxbpel"

dictprocess ={"partnerLinks":{"links":[], "asyncronizeLinks":[]},
                "variables":{"vars":["temp"],"temps":[]},"VPList":{}}
"""
VPList Format is as follows:
{
    "ConfVP":{
        "ConfVPName":{
            "ConfVarName":{
                "ChoiceVP":"ChoiceVar"}
                *
        }*
    }, 
    "VP": {
        "VPName":[Variants]
    } 
}
"""
VPList = {"ConfVP":{},"VP":{}}
mapping = {}
sequence_counter = 1
flow_counter = 1
processId = 1
numbers = "0123456789"
forFirstReceiveOp = ""
FirstReceiveOpSet = False

basic_acts = ["flow", "sequence", "if", "while", "repeatUntil", "forEach", 
              "pick", "receive","reply", "invoke", "assign", "exit","empty"]
receive_pml = "\n"+"%s" + "\tchan_%s?%s;" + "\n"  
reply_pml = "\n"+"%s" + "\tchan_%s!%s;" + "\n"  
invoke_pml = "\n"+"%s" + "\tchan_%s!%s;\n%s\n"
invoke_reply_part = "\tchan_%s?%s;" 
structured_act_pml = "" 
orchProcPml = "active proctype %s(){%s%s}"
if_pml = "\n\tif\n%s\tfi;\n"
while_pml = "\n\tdo\n%s\tod;\n"
repeatUntil_pml = "\n\tdo%s\n"
variation_pml = "\n\tgd\n%s\tdg;\n"

""" Transform BPEL constructs to pml equivalent 
"""
def transform(inFileName):
    doc = etree.parse(inFileName)
    root = doc.getroot()   
    global tempPmlFile
    tempPmlFile = open("temp_"+ rootName+".pml","a")
    extract(root)
    tempPmlFile.close()
    constructPmlFile()

""" Seperate static parts (partnerlinks and variables) and behavioral parts 
    (basic and structured activities) 
"""
def extract(node):
    if getEName(node) == "partnerLink":
        addPartnerLink(node)
    elif getEName(node) == "variable":
        addVariables(node)
    elif getEName(node) in basic_acts or isVP(node):     
        pml = extract_behavioral_model(node)
        addPmlInit(pml)
        return
    children = node.getchildren()
    for child in children:
        extract(child)
        
""" Transform from BPEL activities to pml equivalents
"""
def extract_behavioral_model(node,actName = ""):
    pml = "" 
    if getEName(node) == "receive" or getEName(node) == "reply":
        pml = getrecreppml(node,getEName(node))        
    elif getEName(node) == "invoke":
        pml = getinvokepml(node)
    elif getEName(node) == "assign":
        pml = getassignpml(node)    
    elif getEName(node) == "empty":
        pml = "\n\tskip;\n"
    elif getEName(node) == "exit":
        pml = "\n\tskip;\n"    
    elif getEName(node) == "sequence": 
        pml = addSequence(node)
    elif getEName(node) == "flow":
        pml = addFlow(node)
    elif getEName(node) == "if":
        pml = addIf(node)
    elif getEName(node) == "while": 
        pml = addWhile(node)    
    elif getEName(node) == "repeatUntil":
        pml = addRepeatUntil(node)    
    elif isVxbpelElem(node) and isVP(node):
        pml = addVariantRelatedParts(node) 
    
    return pml         

""" Add init pml construct and orch proctype                    
"""
def addPmlInit(pmlContent): 
    pml = orchProcPml % (rootName, forFirstReceiveOp, pmlContent)   
    tempPmlFile.write(pml)  

""" Checks whether node is a element node or string and send the name 
"""
def getPartnerLinkName(node):
    if type(node) != type (""):    
        return node.attrib["name"].lower()
    else:
        return node

""" Checks whether node is the asyncronizedLinks list or not 
"""
def isInAsncyronizedLinks(node):
    tempList = dictprocess["partnerLinks"]["asyncronizeLinks"]
    for t in tempList:
        if t["name"] == node:
            return True
    return False

""" Add partnerlinks to dictprocess dictrionary                   
"""
def addPartnerLink(node,messageNo=0):
    name = ""    
    if messageNo != 0:
        temp = getPartnerLinkName(node)
        if not isInAsncyronizedLinks(node):        
            listName = "asyncronizeLinks"
            if node in dictprocess["partnerLinks"]["links"]:
                dictprocess["partnerLinks"]["links"].remove(temp)             
            name = {"name":temp,"messageNo":messageNo}
        else: return    
    else:
        listName = "links" 
        name = getPartnerLinkName(node)
    dictprocess["partnerLinks"][listName].append(name)
    
""" Add variables to dictprocess dictionary
"""
def addVariables(node):
    if type(node) != type (""):
        dictprocess["variables"]["vars"].append(node.attrib["name"].lower())
    else:
        dictprocess["variables"]["temps"].append(node)

""" Not converted --> bpel:getVariableProperty('stockResult','inventory:level') > 100
    Converted -->  $orderDetails > 100
    Not converted --> $itemsShipped &lt; bpel:getVariableProperty('shipRequest','props:itemsTotal')

    Parsign bpel conditiona dn convert to pml
    Converted patterns are :
        var1 logicalrelation var2 
        var1 logicalrelation string
        var1 logicalrelation number
    where var1, var2 are "$varname", logicalrelation is "<, > , == , != , &lt; , &gt;"    
"""
def parseCondition(condition):
    scond = condition.strip().split()
    cvar1 = scond[0].strip()[1:]
    logicalRel = scond[1].strip()            
    if logicalRel[0] == "&":
        if logicalRel == "&lt;": logicalRel = "<"
        elif logicalRel == "&gt;": logicalRel = ">"
    cvar2 = scond[2].strip()     
    if cvar2[0] == "$":
        cvar2 = cvar2[1:]
    elif cvar2[0] == "'":
        cvar2 = cvar2[1:-1]
        if not cvar2[0] in numbers:
            addVariables(cvar2)
    processedCond =  "("+cvar1+" "+logicalRel+" "+cvar2+") -> "  
    return processedCond

""" Extract activities under else and elseif parts 
"""
def getActivities(node):
    else_content,condition = "",""    
    children = node.getchildren()
    for child in children:
        if getEName(child) == "condition":
            condition = parseCondition(child.text)
        else:         
            else_content += extract_behavioral_model(child)     
    if condition == "": 
        condition = "else ->"    
    return "\t:: %s%s" % (condition, else_content)   
       
""" Add sequence structured activity
"""
def addSequence(node):   
    children = node.getchildren()   
    pml = "\n"
    for child in children:
        pml += "\t{" + extract_behavioral_model(child) +"\t};\n"        
    return pml 

""" Add flow structured activity
"""
def addFlow(node):
    pml = ""    
    global flow_counter     
    children = node.getchildren()
    for child in children:
        pml += extract_behavioral_model(child)
    return pml

""" Add while structured activity
"""
def addWhile(node):
    pml = ""
    children = node.getchildren()
    while_content = ""     
    for child in children:
        condition = ""
        if getEName(child) == "condition":
            condition = parseCondition(child.text)
            while_content =  "\t:: " + condition                          
        else:
            while_content += "\t{" + extract_behavioral_model(child) + "\t};\n" 
    pml += while_pml % while_content     
    return pml   

""" Add repeat until structured activity
"""
def addRepeatUntil(node):
    children = node.getchildren()
    ru_content = ""     
    pml = ""
    for ind in range(len(children)):
        condition = ""
        if getEName(children[ind]) == "condition":
            condition = parseCondition(children[ind].text)
            ru_content +=  "\tod unless {" + condition[:-4] + ";};"                         
        else:
            if ind == 0:
                ru_content += "\n\t:: {" + extract_behavioral_model(children[ind])[:-1] + "} ->" 
            else:
                ru_content += "\n\t{" + extract_behavioral_model(children[ind])[:-1]+"\n\t};\n"    
    pml += repeatUntil_pml % ru_content     
    return pml     

""" Transform from BPEL if structured activity to pml equivalent
"""
def addIf(node):
    children = node.getchildren()
    if_content,elseif_content = "",""  
    pml = ""   
    for child in children:
        condition,elifCond = "",""
        if getEName(child) == "condition":
            condition = parseCondition(child.text)
            if_content =  "\t:: " + condition                  
        elif getEName(child) == "elseif":
            elseif_content += getActivities(child)            
        elif getEName(child) == "else":
            elseif_content += getActivities(child)       
        else:
            tPml = extract_behavioral_model(child) 
            if tPml.strip()[0] == "{":
                if_content += " temp = 1; \n" + tPml
            else:
                if_content += tPml
    pml += if_pml % (if_content + elseif_content)    
    return pml

""" Transform from VxBPEL Variant Point structure to pml equivalent
"""
def addVariantRelatedParts(node):
    # If preCond is different than empty string, this means that the parent construct is sequence.    
    children = node.getchildren()
    pml = ""       
    pCond = ""
    varpml = ""
    if getEName(children[0]) == "Variants":
        vchildren = children[0].getchildren()
        for vchild in vchildren:
            if getEName(vchild) == "Variant":
                name = vchild.attrib["name"]
                name = getVarName(name[0].upper() + name[1:].lower())
                variation = "\t:: f."+name+"-> "
                pCond = "\t:: else -> skip;\n"  
                bpelCodes = vchild.getchildren()[0].getchildren()
                for i in range(len(bpelCodes)):
                    tPml = extract_behavioral_model(bpelCodes[i])
                    if i == 0 and tPml.strip()[0]=="{":
                        varpml += " temp=1; \n" +tPml
                    else:
                        varpml += "\n" +tPml
                     
                varpml += pCond
                pml += variation_pml % (variation + varpml[1:])
                varpml = ""
    return pml

""" Get variable name within the ones in the feature list
"""    
def getVarName(name):
    varList = dictprocess["Vars4FeatureList"]
    for var in varList:
        index =  var.rfind("_")
        if index != -1 and var[:index] == name:
            return var
    return name
 
""" Transform from BPEL assign basic activity to pml equivalent
"""
def getassignpml(node):
    pml = ""
    varfrom,varto = "",""          
    children = node.getchildren()
    for child in children:
        copy_children = child.getchildren() 
        for cchild in copy_children: 
            if getEName(cchild) == "from":
                if "variable" in cchild.attrib:
                    varfrom = cchild.attrib["variable"]
                else:
                    varfrom = cchild.text.replace("$","")         
            elif getEName(cchild) == "to":
                if "variable" in cchild.attrib:
                    varto = cchild.attrib["variable"]
                else:
                    varto = cchild.text.replace("$","")    
        pml += "\t" + varto + "=" + varfrom + ";\n"
    return "\n"+pml

""" Transform from BPEL receive and reply basic activities to pml equivalents
"""
def getrecreppml(node,act_name):            
    for key in node.attrib:
        node.attrib[key] = node.attrib[key].lower()
    temp_var = ""  
    name = ""        
    if not "variable" in node.attrib:
        temp_var = "\tbyte tempR;\n"
        var = "tempR"
    else:
        var = node.attrib["variable"] 
    addPartnerLink(node.attrib["partnerLink"],1)  
    if act_name == "receive":
        global forFirstReceiveOp
        global FirstReceiveOpSet
        if not FirstReceiveOpSet:
            forFirstReceiveOp = "\n\tchan_"+node.attrib["partnerLink"]+"!"+var+";"
            FirstReceiveOpSet = True
        r_pml = receive_pml %(temp_var,node.attrib["partnerLink"],var)  
    else: 
        r_pml = reply_pml %(temp_var, node.attrib["partnerLink"],var)
    return r_pml

""" Transform from BPEL invoke basic activity to pml equivalent
"""
def getinvokepml(node):
    for key in node.attrib:
        node.attrib[key] = node.attrib[key].lower()
    temp_var = ""          
    if not "inputVariable" in node.attrib:
        temp_var = "\n\tbyte tempI;\n"
        var = "tempI"
    else:
        var = node.attrib["inputVariable"] 
    
    addPartnerLink(node.attrib["partnerLink"],1) 
    if not "outputVariable" in node.attrib:
        replypart = invoke_reply_part % (node.attrib["partnerLink"], "temp")
        i_pml = invoke_pml %(temp_var, node.attrib["partnerLink"], var, replypart)   
    else: 
        replypart = invoke_reply_part % (node.attrib["partnerLink"], node.attrib["outputVariable"])
        i_pml = invoke_pml %(temp_var, node.attrib["partnerLink"], var, replypart)   
    return i_pml

""" Transform from BPEL partnerLinks to pml equivalent channels
    Transform from BPEL variables to pml equivalent variables 
"""
def getChannelsAndVariablesPml():
    pml= ""    
    if dictprocess["partnerLinks"]:
        links = set(dictprocess["partnerLinks"]["links"])
        for link in links:
            pml += "chan chan_%s" %link +"= [0] of {byte};\n"   
        asyncLinks = dictprocess["partnerLinks"]["asyncronizeLinks"]    
        for alink in asyncLinks:
            pml += "chan chan_%s = [%d] of {byte};\n" % (alink["name"] , int(alink["messageNo"]))    
 
    
    if dictprocess["variables"]:
        variables = set(dictprocess["variables"]["vars"])        
        if len(variables) > 0:
            pml += "byte "     
            for v in variables:
                pml += "%s," %v 
            pml = pml[:-1]+";\n\n"

        tvariables = dictprocess["variables"]["temps"]        
        if len(tvariables) > 0:
            pml += "byte "     
            for tv in tvariables:
                pml += "%s," %tv 
            pml = pml[:-1]+";\n\n"
 
    return pml
    
""" Construct final pml file by appending static parts and beahvioral parts
"""
def constructPmlFile():
    tempFile = open("temp_"+ rootName+".pml","r")
    orchPmlFile = open(rootName+".pml","w")
    # Pml equivalent of channels and dataTypes  
    # At the begining of the file
    pml = getChannelsAndVariablesPml() 
    orchPmlFile.write(pml)
    tabNo = 0
    withinProc = False
    for line in tempFile:
        sLine = line.strip()
        if len(sLine) != 0:
            newLine = line
            if withinProc:
                if sLine[:2] == "do" or sLine[:2] == "if" or sLine[:2] == "gd" or sLine[0] == "{": 
                    newLine = "\t"*tabNo+line
                    tabNo += 1
                elif sLine[:2] == "od" or sLine[:2] == "fi" or sLine[:2] == "dg" or sLine[:3] == "};":
                    tabNo -= 1
                    newLine ="\t"*tabNo+line
                    
                else:        
                    if sLine[0] == ":": 
                        if tabNo-1 >= 0:
                            newLine = "\t"*(tabNo-1)+line
                    else:
                        newLine = "\t"*tabNo+line
            orchPmlFile.write(newLine)
        if sLine[:6] == "active":
            withinProc = True
        
    orchPmlFile.close()
    tempFile.close()
    
""" print tree
"""
def printTree(root):
    children = root.getchildren()
    for child in children:
        print getEName(child)

""" Return true/false regarding the node is a VariationPoint   
"""
def isVP(node):
    if node.xpath('namespace-uri(.)') ==  vxbpel_ns and getEName(node)== "VariationPoint":
        return True
    return False

""" Return true/false regarding the node is within vxbpel namespace    
"""
def isVxbpelElem(node):
    if node.xpath('namespace-uri(.)') ==  vxbpel_ns:
        return True
    return False

""" Return the name of the node separated from its namespace   
"""
def getEName(node):
    prefix = node.xpath('namespace-uri(.)').format()
    tag = node.tag
    return tag[tag.find(prefix)+len(prefix)+1:]

""" Extract ConfigurableVariationPoints, regarding Variants and their realizations
    Remove ConfigurableVariationPoints related parts   
    Create a temporary file "temp_orchestrationName.xml" for further processing 
"""
def extractVPs(inFileName):
    doc = etree.parse(inFileName)
    root = doc.getroot()
    
    nsmap =  root.nsmap  
    confVPs =  root.xpath('vxbpel:ConfigurableVariationPoints/vxbpel:ConfigurableVariationPoint',namespaces = nsmap)  
    for cvp in confVPs:
        conf = cvp.attrib["id"]
        VPList["ConfVP"][conf] = {} 
        cvars = cvp.xpath('vxbpel:Variants/vxbpel:Variant',namespaces = nsmap)   
        for v in cvars:
            vname = v.attrib["name"]
            VPList["ConfVP"][conf][vname] = {}
            cs =  v.xpath('vxbpel:RequiredConfiguration/vxbpel:VPChoices/vxbpel:VPChoice',namespaces = nsmap)  
            for c in cs:
                vpname = c.attrib["vpname"]
                varname = c.attrib["variant"]
                VPList["ConfVP"][conf][vname][vpname] = varname
    VPs=  root.xpath('//vxbpel:VariationPoint',namespaces = nsmap)  
    
    for vp in VPs:
        vpName = vp.attrib["name"]
        VPList["VP"][vpName] = []
        vs = vp.xpath('vxbpel:Variants/vxbpel:Variant',namespaces = nsmap)
        for v in vs:
            vName = v.attrib["name"]
            VPList["VP"][vpName].append(vName)    
    dictprocess["VPList"] = VPList
    tempName = createTempFile(inFileName)
    #if file name is added to transformed file name
    #rootName = inFileName[:inFileName.find(".xml")] +"_" +root.attrib["name"]
    return tempName,root.attrib["name"]

""" Remove ConfigurableVariationPoints parts from the 
    "temp_orchestrationName.xml"
"""
def createTempFile(inFileName):
    source = open(inFileName)
    if "/" in inFileName:
        real = os.path.basename(inFileName)
        lastInd = inFileName.rfind("/")
        tempFileName = inFileName[:lastInd+1] + "temp-"+real   
    else:
        tempFileName = "temp-"+inFileName
    
    tempFile = open(tempFileName, "w")
    for line in source:
        if "<vxbpel:ConfigurableVariationPoints>" in line:
            break
        tempFile.write(line)
    tempFile.write("</bpel:process>")
    source.close()    
    tempFile.close()   
    return tempFileName

""" Features datatype in pml file 
    typedef features {
        bool feature;    
        ...
        bool feature
    };
    features f;  
"""
def createPMLFeatures():
    temp = "typedef features {\n"
    for v in dictprocess["Vars4FeatureList"]:
        temp += "\tbool "+v+";\n"
    temp =  temp[:-2] + "\n};\nfeatures f;\n\n"   
    tempPmlFile = open("temp_"+ rootName+".pml","w")
    tempPmlFile.write(temp)
    tempPmlFile.close()

""" Create a TVL File for the use of snip model checker including 
    ConfigurableVariationPoints and VariationPoints   
"""
def createTVL():
    checkNaming()
    tempList = []
    temp = "root %s{\n\tgroup someOf{\n" %(rootName[0].upper() + rootName[1:].lower())
    tablevel = 1    
    confs = VPList["ConfVP"]
    for conf in confs:
        tablevel += 1
        temp += "\t"*tablevel + (conf[0].upper() + conf[1:].lower()) + " group someOf{\n"       
        for cv in confs[conf]:    
            tablevel += 1
            temp += "\t"*tablevel + (cv[0].upper() + cv[1:].lower()) + " group allOf{\n"             
            for c in confs[conf][cv]:
                tablevel += 1
                tempList.append(c) 
                cvar = confs[conf][cv][c]    
                temp += "\t"*tablevel + (cvar[0].upper() + cvar[1:].lower()) +",\n"
                tablevel -= 1             
            temp = temp[:-2] + "\n"+"\t"*tablevel +"},\n"
            tablevel -= 1        
        temp = temp[:-2] + "\n"+"\t"*tablevel +"},\n"
        tablevel -= 1    
    
    vps = VPList["VP"]
    for vp in vps:
        #if not vp in tempList:
        if not isVPInTemplist(vp,tempList):    
            tablevel += 1
            temp += "\t"*tablevel + (vp[0].upper() + vp[1:].lower()) + " group someOf{\n"
            for v in vps[vp]:
                tablevel += 1
                temp += "\t"*tablevel + (v[0].upper() + v[1:].lower()) +",\n"
                tablevel -= 1            
            temp = temp[:-2] + "\n" + "\t"*tablevel +"},\n"           
            tablevel -= 1
    temp = temp[:-2] + "\n"+"\t"*tablevel+"}\n"
    temp += getConstraints()
    temp += "}\n"

    tvlFile = open(rootName+".tvl","w")
    tvlFile.write(temp)    
    tvlFile.close()

""" Get constraints and construct them suited to TVL format
"""    
def getConstraints():
    constraints = ""
    listFeatures = dictprocess["Vars4FeatureList"] 
    for feature in listFeatures:
        for f in listFeatures:
            if feature in f and feature != f:
                constraints += "\t"+feature +" <-> " + f + ";\n" 
    return constraints
    
""" Check whether given variation point (vp) is in tempList  
"""
def isVPInTemplist(vp,tempList):
    vp = vp[0].upper() + vp[1:].lower()
    for item in tempList:
        index = item.rfind("_")
        if index != -1:
            if item[:index] == vp:
                return True
        else:
            if item == vp:
                return True
    return False
    
""" Add item to mapping dictionary. If the item is not in mapping, then add 
    it as is. Otherwise the item name is changed and added under related list. 
"""
def addToMapping(item):
    if not item in mapping:
        nItem = item[0].upper() + item[1:].lower()
        mapping[item] = [nItem]
    else:
        nItem = item[0].upper() + item[1:].lower() + "_" + str(len(mapping[item]))
        mapping[item].append(nItem)
    return nItem

""" Name clashes are discovered, items that have same name are changed and 
    a new dictionary is created.
"""    
def checkNaming():
    newDict = {"ConfVP":{},"VP":{}}
    Vars4FeatureList = []
    addToMapping(rootName)
    global VPList
    confs = VPList["ConfVP"]
    nconf = ""
    for conf in confs:
        nconf = addToMapping(conf)
        newDict["ConfVP"][nconf] = {}
        cvars = confs[conf]
        for cvar in cvars:
            ncvar = addToMapping(cvar)
            newDict["ConfVP"][nconf][ncvar] = {}
            choices = confs[conf][cvar]
            for choice in choices:
                nchoice = addToMapping(choice)
                c = choices[choice]    
                nc = addToMapping(c)
                Vars4FeatureList.append(nc)
                newDict["ConfVP"][nconf][ncvar].update({nchoice:nc})    
    
    
    vps = VPList["VP"]
    for vp in vps:
        newDict["VP"][vp] = []
        for v in vps[vp]:
            if not vp in mapping:
                v = addToMapping(v)
                Vars4FeatureList.append(v)
            else:
                v = v[0].upper() + v[1:].lower()  
            newDict["VP"][vp].append(v)
    
    dictprocess["Vars4FeatureList"] = set(Vars4FeatureList)    
    VPList = newDict
    
def clear_temp(path):
    files = glob.glob(path+'/temp*')
    for f in files:
        os.remove(f)    
    
def main(): 
    orchFileName = "userverification.xml"    
    global rootName
    tempFileName,rootName = extractVPs(orchFileName)
    createTVL()
    createPMLFeatures()
    transform(tempFileName)
    clear_temp(".")
    
if __name__ == '__main__':
    main()












