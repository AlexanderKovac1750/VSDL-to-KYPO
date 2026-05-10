import scripts.utils as utils
import scripts.term_types as tt
import scripts.software_versioning as sv

def add_required_terms(object_name, isNetwork, declared_terms):
    req_terms = set.intersection(set(tt.required_terms), tt.network_attributes if isNetwork else tt.node_attributes)
    object_type = "network" if isNetwork else "node"
    
    for req_term in req_terms:
        term = utils.make_term_name(req_term, object_type, object_name)
        declared_terms.add(term)
    return

def get_term_type(term):

    #extract attribute name
    attribute = utils.break_term_name(term)[0]
    if(attribute.__class__ == tuple):
        attribute = attribute[0]+'.'
    
    if(attribute in tt.bool_terms):
        return "Bool"
    elif(attribute in tt.numeric_terms):
        return "Int"
    elif(attribute in tt.numeric_set_terms):
        return "(Set Int)"
    elif(attribute in tt.string_terms):
        return "String"
    elif(attribute in tt.string_set_terms):
        return "(Set String)"
    elif(attribute in tt.specialized_terms):
         return tt.specialized_terms[attribute]
    else:
        raise Exception(f'unrecognized attribute "{attribute}", unknown type!')

def multiply_value(val, unit):
    multiplicator = 1
    unit = unit.lower()
    
    if(unit.startswith("k")):
        multiplicator = 1_000
    elif(unit.startswith("m")):
        multiplicator = 1_000**2
    elif(unit.startswith("g")):
        multiplicator = 1_000**3
    elif(unit.startswith("t")):
        multiplicator = 1_000**4
    elif(unit.startswith("p")):
        multiplicator = 1_000**5

    try:
        if("." in val):
            val = float(val)
        else:
            val = int(val)
    except:
        raise Exception(f'expected number, instead got "{val}" !')

    return val*multiplicator

def resolve_comparison(attribute, object_type, words, declared_terms):
    quotes = '"' if not attribute in tt.numeric_terms else ""

    #simple non_arithmetic configuration
    if(len(words)==1):
        return "=", f"{quotes}{words[0]}{quotes}"

    #verify required word count
    if(len(words)<3):
        raise Exception("too few words for statement with comparison!")

    #arithmetic configuration
    comp_op = words[0]+" "+words[1]
    if(not comp_op in tt.comparison_ops):
        raise Exception(f'unsupported comparison op "{comp_}" !')
    comp_op = tt.comparison_ops[comp_op]

    #handle relative constraint
    if(words[0] == "same"):
        val = utils.make_term_name(attribute, object_type, words[2])
        declared_terms.add(val)
        return comp_op, val

    #read and format constant
    val = quotes+words[2]+quotes
    words = words[2+1:]
    
    #multiply value
    if(len(words)==1):
        val = multiply_value(val, words[0])

    return comp_op, val

def make_version_statement(software, version_hints, term_version, prefix=""):

    #ignore if no versions are available
    if(len(sv.get_versions(software))==0 and prefix==""):
        return f'(= "Unknown" "Software" "{software}")'
    sub_statements = []

    #parse version hints
    comp_op = None
    version_comp_ops = dict({
        "on":"=",
        "from":"str.>=",
        "above":"str.>",
        "below":"str.<",
        "to":"str.<="
        })
        
    for hint in version_hints:
        if(comp_op is None):
            comp_op = version_comp_ops[hint]
            continue

        #make sub-statement
        #utils.add_available_version(software, comp_op, hint)
        encoded_version = sv.encode_version(hint)

        if(">" in comp_op):
            comp_op = comp_op.replace('>','<')
            partial_statement = f'({comp_op} "{prefix}{encoded_version}" {term_version})'
        else:
            partial_statement = f'({comp_op} {term_version} "{prefix}{encoded_version}")'
        sub_statements.append(partial_statement)
        comp_op = None

    #combine sub-statements
    statement_version = utils.concat(sub_statements, " ")
    if(len(sub_statements)>1):
        statement_version=f"(and {statement_version})"
        
    return statement_version

def resolve_simple_statement(name, isNetwork, words, declared_terms, implications):
    object_type = "network" if isNetwork else "node"
    
    #handle simple statements

    #handle IMPOSSIBLE macro
    if(words==["IMPOSSIBLE"]):
        return '(= 0 1)'

    #detect incomplete short statements
    if(len(words)<3):
        raise Exception(f'unsupported statement, too short [{words}] !')

    #handle user accessible network
    if(isNetwork and words == ["is", "user", "accessible"]):
        term_accessible = utils.make_term_name("accessible", object_type, name)
        declared_terms.add(term_accessible)
        return f'(= {term_accessible} true)'
    
    #handle "is" for OS special case
    if(words[1]=="is" and not isNetwork and words[0]=="OS" and words[2]!="same"):
        os_name, version = sv.extract_software_version(words[2])
        term_os = utils.make_term_name("OS", object_type, name)
        declared_terms.add(term_os)

        #handle comparison ops (above, below...)
        version_hints = words[3:]
        statement_version = ""
        if(version_hints != []):
            statement_version = make_version_statement(os_name, version_hints, term_os, os_name+"-")

        os_v0 = os_name
        os_v1 = os_name

        #make os version boundaries
        if(version is None):
            last_symbol_ASCII = ord(os_v1[-1])
            os_v1 = os_v1[:-1] + chr(last_symbol_ASCII+1)

        else:
            os_v0 += "-" + sv.encode_version(version)
            os_v1 += "-" + sv.encode_version(sv.change_version(version,1))

        #bind node's OS within boundaries
        return f'(and (str.<= "{os_v0}" {term_os}) (str.< {term_os} "{os_v1}") {statement_version})'
    
    #common "is" statements
    direct_keywords = ["type", "flavor", "cpu", "disk", "OS", "memory",
                       "bandwidth", "basebox"]
    if(words[1]=="is" and words[0] in direct_keywords):
        attribute = words[0]

        #categorize attribute
        if not(attribute in (tt.network_attributes if isNetwork else tt.node_attributes)):
            raise Exception(f'unsupported attribute "{attribute}" !')
        is_numeric = attribute in tt.numeric_terms

        #process right side
        term = utils.make_term_name(attribute, object_type, name)
        declared_terms.add(term)
        comp_op, val = resolve_comparison(attribute, object_type, words[2:],declared_terms)

        #handle text values
        if(not is_numeric and comp_op!="="):
            raise Exception(f'arithmetic operation "{comp_op}" used on non-arithmetic attribute "{attribute}" !')
            
        return f"({comp_op} {term} {val})"

    #address range
    ip_range_keyword = ["address","addresses","ip", "IP"]
    if(words[0]in ip_range_keyword and isNetwork and len(words)==6):
        start_ip = words[3]
        end_ip = words[5]

        #parse ip range
        start_ip = utils.make_ip_num(start_ip, 0)
        end_ip = utils.make_ip_num(end_ip, 1)
        net_size = end_ip - start_ip

        if(not net_size in tt.valid_net_sizes):
            raise Exception(f'invalid netsize "{net_size}" of {utils.make_ip_str(start_ip)} network!')

        #declare terms
        term_netid = utils.make_term_name("netid", object_type, name)
        term_netsize = utils.make_term_name("netsize", object_type, name)
        term_connected = utils.make_term_name("connected", object_type, name)

        declared_terms.add(term_netid)
        declared_terms.add(term_netsize)
        declared_terms.add(term_connected)

        #make statements
        statement_netid=f"(= {term_netid} {start_ip})"
        statement_netsize=f"(= {term_netsize} {net_size})"
        statement_connected=f"(<= (set.card {term_connected}) (- {term_netsize} 2))"
        return f"(and {statement_netid} {statement_netsize} {statement_connected})"

    #connected nodes
    if(words[0]=="node" and isNetwork):

        #categorize statement
        specified_ip = words[2]=="has"
        expected_word_count = 5 if specified_ip else 4
        if(len(words)!= expected_word_count):
            raise Exception(f'wrong statement length, expected {expected_word_count}, got {len(words)}!')

        #is connected statement
        connected_node = words[1]
        term_connected = utils.make_term_name("connected", object_type, name)
        declared_terms.add(term_connected)
        statement_connected = f'(set.member "{connected_node}" {term_connected})'

        if(not specified_ip):
            return statement_connected

        #has IP statement
        ip_num = utils.make_ip_num(words[4])
        
        term_connected_specific = utils.make_term_name(("connected",str(ip_num)), object_type, name)
        declared_terms.add(term_connected_specific)
        statement_connected_specific = f'(= {term_connected_specific} "{connected_node}")'
        
        term_netid = utils.make_term_name("netid", object_type, name)
        term_netsize = utils.make_term_name("netsize", object_type, name)
        statement_connected_valid = f'(< {term_netid} {ip_num} (+ {term_netid} {term_netsize} -1))'

        implications[statement_connected_specific]=f'(and {statement_connected} {statement_connected_valid})'
        return statement_connected_specific

    #mounted software
    if(words[0:2]==["mounts","software"] and not isNetwork):
        term_mounted = utils.make_term_name("mounted", object_type, name)
        declared_terms.add(term_mounted)

        software_version = words[2:]
        software, version = sv.extract_software_version(software_version[0])
        
        if(len(software_version)==1 and version is None):
            return f'(set.member "{software}" {term_mounted})'
            
        #handle versioning by adding ::
        version_hints = software_version[1:]+(["on",version] if not version is None else [])
        statement_software = f'(set.member "{software}" {term_mounted})'

        term_version = utils.make_term_name(("mounted",software), object_type, name)
        declared_terms.add(term_version)

        statement_version = make_version_statement(software, version_hints, term_version)
        implications[statement_version]=statement_software
        return statement_version
        
    #access to internet
    internet_access_phrase = ["gateway","has","direct",
                              "access","to","the","Internet"]
    if(words==internet_access_phrase and isNetwork):
        term_internet = utils.make_term_name("internet", object_type, name)
        declared_terms.add(term_internet)
        return f'(= {term_internet} true)'

    #handle users
    if(words[0]=="exists" and words[1] == "user" and not isNetwork):
        user = words[2]
        
        term_users = utils.make_term_name("users", object_type, name)
        declared_terms.add(term_users)
        statement_user = f'(set.member "{user}" {term_users})'

        if(len(words)==3):
            return statement_user

        #users with specified password
        if(words[3:5]==["with","password"] and len(words)==6):
            password = words[5]
            
            term_password = utils.make_term_name(("password",user), object_type, name)
            declared_terms.add(term_password)
            statement_password = f'(= "{password}" {term_password})'

            implications[statement_password]=statement_user
            return statement_password

    #handle files and directories
    if(words[0]=="contains" and not isNetwork and words[1] in ["file","directory"]):
        term = utils.make_term_name("files" if words[1]=="file" else "directories", object_type, name)
        declared_terms.add(term)

        #make statement about filepath existing
        filepath = utils.standardize_path_str(words[2])
        statement_filepath = f'(set.member "{filepath}" {term})'

        #make statement about parent path existing
        parent_path = utils.get_parent_path_str(filepath)
        parent_paths = []

        #gather parent paths
        while(not parent_path is None):
            parent_paths.append(parent_path)
            parent_path = utils.get_parent_path_str(parent_path)

        if(len(parent_paths)!=0):
            term_directory_set = utils.make_term_name("directories", object_type, name)
            declared_terms.add(term_directory_set)
            
            populated_set = utils.build_set(parent_paths,  True, term_directory_set)
            statement_parents = f'(= {populated_set} {term_directory_set})'
            implications[statement_filepath]=statement_parents

        if(len(words)==3):   
            return statement_filepath

        #handle ownership
        if(words[3:5] == ["owned","by"] and len(words)==6):
            user = words[5]

            #check user existance
            term_users = utils.make_term_name("users", object_type, name)
            declared_terms.add(term_users)
            statement_user = f'(set.member "{user}" {term_users})'

            #ensure ownership
            term_owner = utils.make_term_name(("owner",filepath), object_type, name)
            declared_terms.add(term_owner)
            statement_owner = f'(= "{user}" {term_owner})'

            implications[statement_owner]=f'(and {statement_user} {statement_filepath})'
            return statement_owner

    #handle user-file permissions
    permission_keywords = ["read", "write", "execute"]
    if(words[0]=="user" and words[2]== "can" and words[3] in permission_keywords and len(words) == 5):

        #extract parameters
        user = words[1]
        permission = words[3]
        right = words[3]
        path = utils.standardize_path_str(words[4])

        #add permission
        term_permission = utils.make_term_name(("permission",user,path,right),object_type, name)
        declared_terms.add(term_permission)
        statement_permission = f'(= {term_permission} true)'

        #check for user
        term_users = utils.make_term_name("users", object_type, name)
        declared_terms.add(term_users)
        statement_user = f'(set.member "{user}" {term_users})'

        #check whether path exist
        term_file = utils.make_term_name("files", object_type, name)
        declared_terms.add(term_file)
        term_dir = utils.make_term_name("directories", object_type, name)
        declared_terms.add(term_dir)
        statement_path = f'(or (set.member "{path}" {term_file}) (set.member "{path}" {term_dir}))'

        implications[statement_permission] = f'(and {statement_user} {statement_path})'
        return statement_permission

    #handle sudoers
    if(words[0]=="user" and words[2:4]==["can","sudo"] or words[2:4]==["is","administrator"]):
        user = words[1]

        term_sudoers = utils.make_term_name("sudoers", object_type, name)
        declared_terms.add(term_sudoers)
        statement_sudo = f'(set.member "{user}" {term_sudoers})'

        #prepare implication
        term_users = utils.make_term_name("users", object_type, name)
        declared_terms.add(term_users)
        statement_user = f'(set.member "{user}" {term_users})'

        implications[statement_sudo]=statement_user
        return statement_sudo

    #handle firewall
    if(words[0]=="firewall" and isNetwork and len(words) in [4,6]):

        #get action and address type
        rule=words[1]
        if(not rule in ["blocks","forwards"]):
            raise Exception(f'unrecognized firewall rule "{rule}" !')

        address_type=words[2].lower()
        if(not address_type in ["port","ip"]):
            raise Exception(f'unrecognized address type "{address_type}" !')

        #get address numerical value
        address = words[3]
        if(address_type=="ip"):
            address = utils.make_ip_num(address)
        address=int(address)

        #blocked addresses
        if(rule=="blocks"):
            term_block = utils.make_term_name((rule, address_type), object_type, name)
            declared_terms.add(term_block)
            return f'(set.member {address} {term_block})'

        #forwarded addresses
        elif(len(words)==6):
            term_forward = utils.make_term_name((rule, address_type, str(address)), object_type, name)
            declared_terms.add(term_forward)
            
            #get destination address numerical value
            dst_address = words[5]
            if(address_type=="ip"):
                dst_address = utils.make_ip_num(dst_address)

            return f'(= {dst_address} {term_forward})'
        
    statement_str = utils.concat(words," ")
    raise Exception(f'unrecognized statement "{statement_str}" !')
