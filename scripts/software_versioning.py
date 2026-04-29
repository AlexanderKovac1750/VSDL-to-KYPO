import scripts.utils as utils

verion_separators = ['.','@']
def extract_software_version(software_version, formal_syntax=True):

    #strip version
    software = software_version.rstrip("0123456789" + (verion_separators[0] if formal_syntax else verion_separators[1]))
    if(software == software_version or software_version[len(software)-1]!='-'):
        return software_version, None

    #extract version and software name
    version = software_version[len(software):]
    software = software[:-1]
    
    if(version==""):
        return software_version, None
    return software, version

def encode_version(raw_version):
    version = ""
    
    for segment in raw_version.split(verion_separators[0]):
        padding = verion_separators[1]*len(segment)
        version += padding+segment

    return version

def decode_version(encoded_version):
    segments = encoded_version.split(verion_separators[1])
    decoded_version = utils.concat(segments,verion_separators[0])
    return decoded_version

def change_version(version, direction):
    #split to version segments
    segments = version.split(verion_separators[0])
    last_segment = int(segments.pop(-1))
        
    #remove trailing 0.0.0... => 1.24.0.0 --> 1.24
    while(last_segment==0 and direction <0 ):
        last_segment = int(segments.pop(-1))

    #inc/dec and recombine
    last_segment += direction
    segments.append(str(last_segment))
    return utils.concat(segments,verion_separators[0])

#load versioning and basebox info
versioned_software = None

def load_data():
    global versioned_software

    #load available software versions
    if(versioned_software is None):
        versioned_software = utils.load_yaml("data/softwares.yml")

def get_versions(software):
    load_data()
    global versioned_software

    #check software deployment scripts
    available_versions = set()
    if(software in versioned_software):
        for entry in versioned_software[software]:
            available_versions.add(str(entry["version"]))

    #check baseboxes
    utils.get_basebox_info(None)
    for base_box, BB_props in utils.base_boxes.items():
        if(not "preconfigured_software" in BB_props):
            continue
        if(not software in BB_props["preconfigured_software"]):
            continue
        available_versions.add(str(BB_props["preconfigured_software"][software]))
    return available_versions

def get_version_requirements(device, software, version):
    load_data()
    global versioned_software

    #get OS and BB terms
    term_basebox = utils.make_term_name("basebox", "node", device)
    term_OS = utils.make_term_name("OS", "node", device)
    term_version = utils.make_term_name(("mounted", software), "node", device)
    
    supported_BBs = []
    supported_OSs = []

    #get valid deployment scripts configurations
    if(software in versioned_software):
        for entry in versioned_software[software]:
            if(entry["version"]!=version):
                continue
            
            if("base_boxes" in entry):
                supported_BBs += entry["base_boxes"]

            if("OS" in entry["version"]):
                supported_OSs += entry["OS"]

    #parse into set to remove duplicates
    supported_OSs=set(supported_OSs)
    supported_BBs=set(supported_BBs)

    #get valid pre-installed base box configurations
    for base_box in utils.base_boxes:
        BB_info = utils.get_basebox_info(base_box)

        #add BB if OS is supported
        if(BB_info["OS"] in supported_OSs):
            supported_BBs.add(base_box)

        #ignore other softwares/versions
        if(not "preconfigured_software" in BB_info):
            continue
        if(not software in BB_info["preconfigured_software"]):
            continue

        #resolve conflicting versions
        if(BB_info["preconfigured_software"][software]==version):
            supported_BBs.add(base_box)
        elif(base_box in supported_BBs):
            supported_BBs.remove(base_box)

    #return None if no base box supports this software-version
    if(len(supported_BBs)==0):
        return None

    #make main statement
    BB_set = utils.build_set(list(supported_BBs), True)
    statement_basebox = f'(set.member {term_basebox} {BB_set})'
    
    encoded_version = encode_version(version)
    statement_specific_version = f'(= {term_version} "{encoded_version}")'
    return f'(=> {statement_specific_version} {statement_basebox})'

#get software deployment scripts
def get_ansible_scripts(base_box, software, version):

    #ignore if basebox has already installed software
    BB_info = utils.get_basebox_info(base_box)
    if("preconfigured_software" in BB_info):
        if(software in BB_info["preconfigured_software"]):
            preconfigured_version = str(BB_info["preconfigured_software"][software])
            if(version == preconfigured_version):
                return []

    #find suitable script
    load_data()
    global versioned_software
    
    #check entries for software on desired version
    for entry in versioned_software[software]:
        if(entry["version"]!=version):
            continue
        
        #ignore unsupported BBs or OSs
        unsupported = True
        if("base_boxes" in entry and base_box in entry["base_boxes"]):
            unsupported = False
        elif("OS" in entry and BB_info["OS"] in entry["OS"]):
            unsupported = False
        if(unsupported):
            continue

        return entry["ansible"]

    raise Exception(f'no ansible script or base box found for {software}-{version} !')
    
