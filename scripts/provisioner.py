import scripts.utils as utils
import scripts.software_versioning as sv
import copy

default_dir_rights = ["r","x"]
default_file_rights = ["r"]
default_owner_rights = ["r","w","x"]

def generate_acl_mode(filepath, user, config):
    acl_rights = set()

    #get default rights
    if("owner" in config and filepath in config["owner"] and config["owner"][filepath]==user):
        acl_rights = set(default_owner_rights)
    elif("files" in config and filepath in config["files"]):
        acl_rights = set(default_file_rights)
    else:
        acl_rights = set(default_dir_rights)

    #modify based on permission rules
    for acl_code in config["permissions"][user][filepath]:
        if(acl_code.startswith('!')):
            acl_rights.remove(acl_code[1:])
        else:
            acl_rights.add(acl_code)

    #concat acl rights to acl mode
    acl_mode = utils.concat(sorted(acl_rights))
    if(acl_mode == ""):
        acl_mode="-"
    return acl_mode

def make_playbook(hosts):

    playbook = []
    for host in hosts:
        task_configure = dict({
        "hosts":host,
        "become":True,
        "roles":[host]
        })
        
        playbook.append(task_configure)

    return playbook

def generate_directories(path, config):
    if(not "directories" in config):
        return

    for directory in sorted(config["directories"]):
        dir_path = utils.standardize_path_str(path + "/" + directory)
        utils.create_dir_recursively(dir_path)

    return

def generate_files(path, config):
    if(not "files" in config):
        return
    
    #prepeare files folder
    path = utils.standardize_path_str(path)
    generate_directories(path, config)

    #make files
    for filename in config["files"]:
        file = open(path+"/"+filename, 'a')
        file.close()

def provision_vars(host, config):
    variables = dict()

    #add sudoers
    if("sudoers" in config):
        sudoer_list = list()

        for sudoer in config["sudoers"]:

            
            #get password
            password = sudoer
            if("password" in config and sudoer in config["password"]):
                password = config["password"][sudoer]

            #make entry for user list 
            sudoer_entry = dict({
                "name":sudoer,
                "password":password
                })
            sudoer_list.append(sudoer_entry)
            config["users"].remove(sudoer)
            
        variables["sudoer_list"]=sudoer_list

    #add users to user list
    if("users" in config):
        user_list = list()
        for user in config["users"]:

            #check for spaces
            if(' ' in user):
                raise Exception(f'username "{user}" contains whitespace character !')

            #get password
            password = user
            if("password" in config and user in config["password"]):
                password = config["password"][user]

            #make entry for user list
            user_entry = dict({
                "name":user,
                "password":user
                })
            user_list.append(user_entry)
            
        variables["user_list"]=user_list
    
    #add files to file list
    if("files" in config):
        file_list = []
        for file in config["files"]:

            owner = "root"
            if("owner" in config and file in config["owner"]):
                owner = config["owner"][file]
                
            file_entry = dict({
                "path":file,
                "owner":owner
                })
            file_list.append(file_entry)
            
        variables["file_list"]=file_list

    #add directories to directory list
    if("directories" in config):
        directory_list = []
        for directory in config["directories"]:

            owner = "root"
            if("owner" in config and directory in config["owner"]):
                owner = config["owner"][directory]
                
            dir_entry = dict({
                "path":directory,
                "owner":owner
                })
            directory_list.append(dir_entry)
        
        variables["directory_list"]=directory_list

    #add permission to permission_list
    if("permissions" in config):
        permission_list = []

        #go through permissions
        for user in config["permissions"]:
            for filepath in config["permissions"][user]:

                #create permit
                mode = generate_acl_mode(filepath, user, config)
                new_permit = dict({
                    "path":filepath,
                    "user":user,
                    "mode":mode
                    })
                permission_list.append(new_permit)
                
        variables["permission_list"]=permission_list

    #add blocked ports
    if("blocks" in config and "port" in config["blocks"]):
        blocked_ports=[]
        
        for port in config["blocks"]["port"]:
            blocked_port = dict({
                "port":str(port["dst"]),
                "source":port["src"]
                })
            
            blocked_ports.append(blocked_port)
        variables["blocked_ports"]=blocked_ports

    #add blocked ips
    if("blocks" in config and "ip" in config["blocks"]):
        blocked_ips=[]
        for ip in config["blocks"]["ip"]:
            blocked_ip = dict({
                "ip":str(ip["dst"]),
                "source":ip["src"]
                })
            
            blocked_ips.append(blocked_ip)
        variables["blocked_ips"]=blocked_ips

    #add forward ports
    if("forwards" in config and "port" in config["forwards"]):
        forward_ports=[]

        #go over port forwarding solution
        for port in config["forwards"]["port"]:   
            forward_port = dict({
                "port":str(port),
                "to_port":str(config["forwards"]["port"][port]["dst"]),
                "source":config["forwards"]["port"][port]["src"]
                })
            forward_ports.append(forward_port)
        variables["forward_ports"]=forward_ports

    #add forward ips
    if("forwards" in config and "ip" in config["forwards"]):
        forward_ips=[]

        #go over ip forwarding solution                    
        for ip in config["forwards"]["ip"]:
            forward_ip = dict({
                "ip":str(ip),
                "to_ip":str(config["forwards"]["ip"][ip]["dst"]),
                "source":config["forwards"]["ip"][ip]["src"]
                })
                              
            forward_ips.append(forward_ip)
        variables["forward_ips"]=forward_ips
    

    return variables

def provision_software(host, config):
    tasks=[]

    #ignore if no software was specified
    if(not "mounted" in config):
        return []

    #seperate versioned and unversioned softwares
    versioned = []
    unversioned = []
    
    for software in config["mounted"]:
        if("versions" in config and software in config["versions"]):
            versioned.append(software)
        else:
            unversioned.append(software)

    #handle versioned software
    for software in versioned:
        version = config["versions"][software]
        tasks += sv.get_ansible_scripts(config["basebox"], software, version)

    #handle unversioned software
    if(len(unversioned)!=0):
        
        install_mounted = dict()
        install_mounted["name"]="Install packages"
        
        install_mounted["apt"]=dict({
            "name":unversioned,
            "update_cache":True,
            "state":"present"
            })
        tasks.append(install_mounted)
        
    return tasks

def provision_tasks(host, config):
    tasks=[]

    #add base box tasks
    BB_info = utils.get_basebox_info(config["basebox"])
    if("ansible" in BB_info):
        tasks+=BB_info["ansible"]

    #handle user generation
    if("users" in config):
        create_users = dict()
        create_users["name"]="Create users"
        
        create_users["user"]=dict({
            "name":"{{ item.name }}",
            "password":'{{ item.password | password_hash("md5")}}',
            "create_home":"yes",
            "shell":"/bin/bash"
            })
        create_users["loop"]="{{ user_list }}"
        tasks.append(create_users)

    #make sudoers
    if("sudoers" in config):
        check_wheel = dict({
            "name":"Check wheel group",
            "group":dict({
                "name":"wheel",
                "state":"present"
                })
            })
        tasks.append(check_wheel)

        sudo_wheel = dict({
            "name":"Allow wheel group to have sudo",
            "lineinfile":dict({
                "dest":"/etc/sudoers",
                "state":"present",
                "regexp":"^%wheel",
                "line":"%wheel    ALL=(ALL:ALL) NOPASSWD:ALL",
                "validate":"visudo -cf %s"
                })
            })
        tasks.append(sudo_wheel)
        
        create_sudoers = dict()
        create_sudoers["name"]="Create sudoers"
        
        create_sudoers["user"]=dict({
            "name":"{{ item.name }}",
            "password":'{{ item.password | password_hash("md5")}}',
            "group":"wheel",
            "append":"yes",
            "create_home":"yes",
            "shell":"/bin/bash"
            })
        create_sudoers["loop"]="{{ sudoer_list }}"
        tasks.append(create_sudoers)
        
    #handle directories
    if("directories" in config):
        create_directories = dict()
        create_directories["name"]="Create directories"

        create_directories["file"]=dict({
            "path":"/{{ item.path }}",
            "state":"directory",
            "mode":"0755",
            "owner":"{{ item.owner }}"
            })
        create_directories["loop"]="{{ directory_list }}"
        tasks.append(create_directories)

    #handle files
    if("files" in config):
        copy_files = dict()
        copy_files["name"]="Copy files"

        copy_files["copy"]=dict({
            "src":"../files/{{ item.path }}",
            "dest":"/{{ item.path }}",
            "mode":"0744",
            "owner":"{{ item.owner }}"
            })
        copy_files["loop"]="{{ file_list }}"
        tasks.append(copy_files)

    #change permissions
    if("permissions" in config):
        setfacl = dict()
        setfacl["name"]="Modify ACL"

        setfacl["acl"]=dict({
            "default":False,
            "state":"present",
            "entity":"{{ item.user }}",
            "etype":"user",
            "path":"/{{ item.path }}",
            "permissions":"{{ item.mode }}"
            })
        setfacl["loop"]="{{ permission_list }}"
        tasks.append(setfacl)
    
    tasks += provision_software(host, config)

    #handle blocked ports
    if("blocks" in config and "port" in config["blocks"]):
        block_ports = dict()
        block_ports["name"]="Block ports"
        block_ports["become"]="yes"
        
        block_ports["iptables"]=dict({
            "chain":"FORWARD",
            "destination_port":"{{ item.port }}",
            "source":"{{ item.source }}",
            "protocol":"tcp",
            "jump":"DROP"
            })
        block_ports["loop"]="{{ blocked_ports }}"
        tasks.append(block_ports)
                              
    #handle blocked ips
    if("blocks" in config and "ip" in config["blocks"]):
        block_ips = dict()
        block_ips["name"]="Block ips"
        block_ips["become"]="yes"
        
        block_ips["iptables"]=dict({
            "chain":"FORWARD",
            "destination":"{{ item.ip }}",
            "source":"{{ item.source }}",
            "protocol":"tcp",
            "jump":"DROP"
            })
        block_ips["loop"]="{{ blocked_ips }}"
        tasks.append(block_ips)

    #handle forwarded ports
    if("forwards" in config and "port" in config["forwards"]):
        forward_ports = dict()
        forward_ports["name"]="Forward ports from network"
        forward_ports["become"]="yes"
        
        forward_ports["iptables"]=dict({
            "table":"nat",
            "chain":"PREROUTING",
            "destination_port":"{{ item.port }}",
            "to_destination":":{{ item.to_port }}",
            "protocol":"tcp",
            "jump":"DNAT",
            "source":"{{ item.source }}"
            })
        forward_ports["loop"]="{{ forward_ports }}"
        tasks.append(forward_ports)

        #apply forwarding in both directions
        forward_ports = copy.deepcopy(forward_ports)
        forward_ports["iptables"].pop("source")
        forward_ports["name"]="Forward ports to network"
        forward_ports["iptables"]["destination"]="{{ item.source }}"
        tasks.append(forward_ports)
        
    #handle forwarded ips
    if("forwards" in config and "ip" in config["forwards"]):
        forward_ips = dict()
        forward_ips["name"]="Forward ips"
        forward_ips["become"]="yes"
        
        forward_ips["iptables"]=dict({
            "table":"nat",
            "chain":"PREROUTING",
            "destination":"{{ item.ip }}",
            "to_destination":"{{ item.to_ip }}",
            "protocol":"tcp",
            "jump":"DNAT"
            })
        forward_ips["loop"]="{{ forward_ips }}"
        tasks.append(forward_ips)

    return tasks

def provision(output_folder, hosts):

    #clean previous output
    None

    #make simple playbook
    prov_dir = output_folder + "/sandbox/provisioning"
    playbook = make_playbook(hosts)
    utils.save_file((prov_dir,"playbook.yml"), playbook)

    #go over hosts
    for host in hosts:

        #make host_vars
        standard_host_vars = dict({"ansible_python_interpreter":"python3"})
        utils.save_file((prov_dir+"/host_vars/",host+".yaml"), standard_host_vars)
        
        #create tasks
        tasks = provision_tasks(host, hosts[host])
        utils.save_file((prov_dir+"/roles/"+host+"/tasks","main.yml"), tasks)
        
        #create vars
        variables = provision_vars(host, hosts[host])
        utils.save_file((prov_dir+"/roles/"+host+"/vars","main.yml"), variables)

        #create files
        generate_files(prov_dir+"/roles/"+host+"/files", hosts[host])
