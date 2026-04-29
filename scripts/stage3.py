import cvc5
import scripts.utils as utils
import random
import json
import scripts.term_types as tt
import scripts.software_versioning as sv

def assign_firewall_rules(routers, networks):
    possible_rule = [("blocks","port"), ("blocks", "ip"),
                     ("forwards","port"), ("forwards","ip")]

    #copy rules to routers
    for network in networks:
        for connection in networks[network]["connected"]:

            #skip non routers
            if(not connection in routers):
                continue
            
            #add firewall entries to router
            for i in range(4):
                action, address_type = possible_rule[i]

                #skip rule if it's not present in network
                if(not action in networks[network]):
                    continue
                if(not address_type in networks[network][action]):
                    continue
                
                #make lists for rules in routers
                if(not action in routers[connection]):
                    routers[connection][action]=dict()
                if(not address_type in routers[connection][action] and action=="blocks"):
                    routers[connection][action][address_type]=list()
                if(not address_type in routers[connection][action] and action=="forwards"):
                    routers[connection][action][address_type]=dict()

                #add entries
                for entry in networks[network][action][address_type]:
                    if(action=="blocks"):
                        blocked = dict({
                            "dst":entry,
                            "src":networks[network]["netid"]
                            })
                        routers[connection][action][address_type].append(blocked)
                    elif(action=="forwards"):
                        forwarded = dict({
                            "dst":networks[network][action][address_type][entry],
                            "src":networks[network]["netid"]
                            })
                        routers[connection][action][address_type][entry]=forwarded

    #remove rules from networks
    for network in networks:
        if("blocks" in networks[network]):
            networks[network].pop("blocks")
        if("forwards" in networks[network]):
            networks[network].pop("forwards")
    return

def classify_nodes(nodes, router_names):
    hosts=dict()
    routers=dict()

    #seperate hosts from routers
    for node in nodes:
        should_be_router = node in router_names
        is_router = nodes[node]["type"]=="router" if ("type" in nodes[node]) else should_be_router

        #check for conflicting type
        if(should_be_router!=is_router):
            raise Exception(f'node "{node} type should be router, but is "{nodes[node]["type"]}" !')

        if(is_router):
            routers[node]=nodes[node]
        else:
            hosts[node]=nodes[node]

    return hosts, routers

def get_routers(nodes):
    routers = set()
    for node in nodes:
        if("type" in nodes[node] and nodes[node]["type"]=="router"):
            routers.add(node)

    return routers

def check_default_gateway(net_id, used_ips, unspecified, routers, ip_mappings):
    picked_router = None
    DG_ip = net_id+1
    DG_ip_str = utils.make_ip_str(DG_ip)

    #try find picked router
    if(DG_ip in used_ips):
        for it in ip_mappings.items():
            if(it[1]==DG_ip_str):
                picked_router = it[0]
                
    #try to pick router
    else:
        possible_routers = set.intersection(unspecified, routers)
        n = len(possible_routers)

        #DG router not specific enough or unknown
        if(n==0):
            raise Exception(f'no possible default gateway for network {utils.make_ip_str(net_id)} !')
            
        if(n>1):
            raise Exception(f'{n} possible default gateways for network {utils.make_ip_str(net_id)} !')

        picked_router = list(possible_routers)[0]

    if(picked_router is None):
        raise Exception("failed to pick router for default gateway!")
       
    #pick router 
    routers.add(picked_router)

    #specify DG router's ip
    if(picked_router in unspecified):
        ip_mappings[picked_router]=DG_ip_str
        used_ips.add(DG_ip)
        unspecified.remove(picked_router)

def generate_ip(net_id, net_size, used_ips):
    ip_num = random.randint(2,net_size-2-len(used_ips))+net_id

    #avoid conflicting ips
    for used_ip in sorted(used_ips):
        if(used_ip<=ip_num):
            ip_num+=1

    #check whether ip's within net ip range
    if(ip_num>=net_size+net_id):
        raise Exception(f'generated ip "{utils.make_ip_str(ip_num)}" outside of range!')

    return utils.make_ip_str(ip_num)

def assign_ips(network, routers):

    #get connections
    connected_nodes = network["connected"]
    ip_mappings = dict()
    used_ips = set()
    to_be_removed = set()

    #get specific ips
    for entry in network:

        #skip non connections
        if(not entry[0]=="connected"):
            continue

        #generate ip mapping
        ip_num = int(entry[1])
        ip_str = utils.make_ip_str(ip_num)
        connected_node = network[entry].strip('"')

        #remember ip mapping
        if(connected_node in connected_nodes):
            ip_mappings[connected_node]=ip_str
        used_ips.add(ip_num)
        
        #remove old entry
        to_be_removed.add(entry)

    #remove old connections
    for entry in to_be_removed:
        network.pop(entry)

    #get netid, netsize and unspecified connections
    net_id = network["netid"]
    net_size = network["netsize"]
    unspecified = set(connected_nodes) - set(ip_mappings.keys())
            
    #determine default gateway if necessary
    check_default_gateway(net_id, used_ips, unspecified, routers, ip_mappings)
    
    #specify unspecified connections
    for connected_node in unspecified:

        #generate ip
        ip_mappings[connected_node]=generate_ip(net_id, net_size, used_ips)

    #update network ip properties
    network["connected"]=ip_mappings
    network["netid"]=utils.make_ip_str(net_id, net_size)
    network.pop("netsize")
    return

def format_firewall(network):

    #handle blocked addresses
    if(("blocks","ip") in network or ("blocks","port") in network):
        network["blocks"]=dict()

        #extract blocked ips
        if(("blocks","ip") in network):
            ips = network.pop(("blocks","ip"))

            #format ips
            for index, ip in enumerate(ips):
                ips[index]=utils.make_ip_str(ip)
            network["blocks"]["ip"]=ips

        #extract blocked ports
        if(("blocks","port") in network):
            ports = network.pop(("blocks","port"))
            network["blocks"]["port"]=ports
            
    #detect firewall forwards
    firewall_forward = set()
    for attribute in network:
        if(attribute[0]=="forwards"):
            firewall_forward.add(attribute)

    #return if firewall is finished
    if(len(firewall_forward)==0):
        return

    #build dictionary of forwards
    forward_map = dict()
    for forward_entry in firewall_forward:

        #extract forward entry info
        address_type = forward_entry[1]
        src = int(forward_entry[2])
        dst = network.pop(forward_entry)

        #create missing dict
        if(not address_type in forward_map):
            forward_map[address_type]=dict()

        #format ip addresses
        if(address_type=="ip"):
            src=utils.make_ip_str(src)
            dst=utils.make_ip_str(dst)

        forward_map[address_type][src]=dst
    
    network["forwards"]=forward_map
    return

def format_mounted(node):
    
    #get entries
    software_versions = set()
    for entry in node:
        if(entry[0]=="mounted"):
           software_versions.add(entry)

    #skip if no version are specified
    if(len(software_versions)==0):
        return

    #process softwares with specified version
    for software_version in software_versions:
        software = software_version[1]

        #extract version
        version = node.pop(software_version)
        version = sv.decode_version(version)

        #skip unsued software
        if(not software in node["mounted"]):
            continue

        if(not "versions" in node):
            node["versions"]=dict()
            
        node["versions"][software]=version
    return

def format_permissions(node):
    
    #get entries
    permissions = set()
    for entry in node:
        if(entry[0]=="permission"):
           permissions.add(entry)
           
    #skip if no permission are specified
    if(len(permissions)==0):
        return

    acl_codes =dict({
        (True,"read"):"r",
        (False,"read"):"!r",
        (True,"write"):"w",
        (False,"write"):"!w",
        (True,"execute"):"x",
        (False,"execute"):"!x",
        })

    #format user permissions
    user_permissions = dict()
    for permission in permissions:

        #extract permission details and remove used entry
        tmp, user, path, right = permission
        enabled = node.pop(permission)

        #check whether user was created
        if(not user in node["users"]):
            continue

        #check whether file/dir exist
        file_exist = False if not "files" in node else path in node["files"]
        dir_exist = False if not "directories" in node else path in node["directories"]
        if((not file_exist) and (not dir_exist)):
            continue

        #make entry for user
        if(not user in user_permissions):
            user_permissions[user]=dict()

        #make entry for path
        if(not path in user_permissions[user]):
            user_permissions[user][path]=set()

        #add access rights
        acl_code = acl_codes[(enabled,right)]
        user_permissions[user][path].add(acl_code)

    for user in user_permissions:
        for path in user_permissions[user]:
            user_permissions[user][path]=list(user_permissions[user][path])
            
    node["permissions"]= user_permissions
    return

def format_node(node):

    #assign permissions and software versions
    format_permissions(node)
    format_mounted(node)

    #reformat OS version
    os_name, version = sv.extract_software_version(node["OS"], False)
    if(not version is None):
        os_name += "-"+sv.decode_version(version)
    node["OS"] = os_name

    #expand simple tuples
    tupple_attributes = set()
    for attribute in node:
        if(attribute.__class__==tuple and len(attribute)==2):
            tupple_attributes.add(attribute)

    #replace tupples with nested dictionaries
    for tuple_attr in tupple_attributes:
        main_attr, sub_attr = tuple_attr

        if(not main_attr in node):
            node[main_attr]=dict()

        node[main_attr][sub_attr]=node.pop(tuple_attr)
    
    return

def handle_image_specifics(node, images):
    base_box = node["basebox"]
    if(not base_box in images):
        raise Exception('unrecognized base box "{base_box}" !')
    image = images[base_box]

    if("keyring_url" in image and "keyring_path" in image):
        node["keyring_url"] = image["keyring_url"]
        node["keyring_path"] = image["keyring_path"]
    return

def format_solution(networks, nodes):

    #format nodes and get routers
    limits = utils.load_json("data/limits.json")
    images = limits["base_boxes"]["allowed"]
    
    for entry in nodes:
        format_node(nodes[entry])
        #handle_image_specifics(nodes[entry], images)
    routers = get_routers(nodes)

    #assign ips to nodes
    for entry in networks:
        assign_ips(networks[entry], routers)
        format_firewall(networks[entry])
        
    return routers

def extract_objects(configuration):
    networks = dict()
    nodes = dict()
    scenario_name = "generated_game"

    for term in configuration:
        attribute, object_type, object_name = utils.break_term_name(str(term))

        #ignore contraint and helper terms
        if(object_type == "limit"):
            continue
        if(object_type == "getter"):
            continue

        #get term type
        term_type = attribute
        if(attribute.__class__ == tuple):
            term_type = attribute[0]+"."

        #parse value
        value = str(configuration[term]).strip('"')
        if(term_type in tt.bool_terms):
            value = bool(value == "true")
        elif(term_type in tt.numeric_terms):
            value = int(value)
        elif(term_type in tt.numeric_set_terms):
            value = utils.parse_set_syntax(value, True)
        elif(term_type in tt.string_set_terms):
            value = utils.parse_set_syntax(value, False)
            
        #extract network
        if(object_type == "network"):
            if(not object_name in networks):
                networks[object_name]=dict()
            networks[object_name][attribute]=value

        #extract nodes
        elif(object_type == "node"):
            if(not object_name in nodes):
                nodes[object_name]=dict()
            nodes[object_name][attribute]=value

        #extract scenario name
        elif(object_type == "name"):
            scenario_name = value
            
        else:
            #shouldn't be called,
            #since we don't declare such terms in specifier stage
            print(attribute, object_type, object_name, configuration[term])

    return scenario_name, networks, nodes

def find_solution(assertions):
    valid_config = dict()

    #find empty and comment lines
    to_be_removed = list()
    for index, line in enumerate(assertions):
        if(line.startswith(';') or line=="\n"):
            to_be_removed.append(index)
            
    #remove empty and comment lines
    to_be_removed.reverse()
    for index in to_be_removed:
        assertions.pop(index)
    
    #prepare solver
    tm = cvc5.TermManager()
    slv = cvc5.Solver(tm)
    slv.setLogic('QF_SLIAUFFS')

    #set options for debugging and performance
    slv.setOption('produce-models', 'true')
    slv.setOption('produce-unsat-cores', 'true')
    slv.setOption('minimal-unsat-cores', 'true')
    slv.setOption('simplification-bcp', 'true')
    slv.setOption('tlimit-per','25000')

    #prepare statements
    statements=utils.concat(assertions)
    
    #prepare parser
    parser = cvc5.InputParser(slv)
    parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, statements, "MyInput")
    sm = parser.getSymbolManager()

    #parse assertions
    statement_index = 0
    while True:
        try:
            cmd = parser.nextCommand()
            statement_index+=1
            
            if cmd.isNull():
                break
            cmd.invoke(slv, sm)
        except:
            bad_assert = assertions[statement_index]
            raise Exception(f'failed at statement "{bad_assert}" !')

    #check satisfiability
    res = str(slv.checkSat())
    if(res == "unsat"):

        #extract unsatifiable assertions
        bad_core = slv.getUnsatCore()
        problematic_terms = utils.extract_terms(bad_core)
        filtered_terms = []

        #get problematic declared terms
        for term in problematic_terms:
            if(str(term.getKind()) == "Kind.CONSTANT"):
                filtered_terms.append(str(term))

        #decode term name
        for index, term in enumerate(filtered_terms):
            parts = utils.break_term_name(term)

            #decode special characters
            if(parts[0].__class__==tuple):
                parts=list(parts)
                parts[0]=utils.concat(parts[0],'.')

            #replace terms with decode
            decoded_term=utils.concat(parts,'_')
            filtered_terms[index]=decoded_term
            
            for index, assertion in enumerate(bad_core):
                assertion=str(assertion)
                bad_core[index]=assertion.replace(term,decoded_term)

        #generate debug message
        msg ="failed to find valid configuration for terms:\n"
        for term in filtered_terms:
            msg+=" - "+term+"\n"
        msg+=f"and assertions:\n{bad_core} !"
        raise Exception(msg)
        
    if(res != 'sat'):
        raise Exception(f"{res}, unsatisfiable constraints!")
    
    terms = sm.getDeclaredTerms()
    values = slv.getValue(terms)

    for i in range(len(terms)):
        valid_config[terms[i]] = values[i]

    return valid_config

def main():
    lines = utils.read_file("cache/assertions.smt2")
    valid_config = find_solution(lines)
    scenario_name, networks, nodes = extract_objects(valid_config)
    
    router_names = format_solution(networks, nodes)
    networks = utils.sort_dict(networks)
    nodes = utils.sort_dict(nodes)
    
    hosts, routers = classify_nodes(nodes, router_names)
    assign_firewall_rules(routers, networks)
    
    data = dict({"name":scenario_name, "networks" : networks, "hosts" : hosts, "routers" : routers})
    utils.save_file("cache/solution.json", data)
