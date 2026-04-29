import scripts.utils as utils
import sys
import scripts.provisioner as prov

def define_base_box(image, limits):
    available = limits["base_boxes"]["allowed"]
    base_box = dict()
    
    base_box["image"]=image
    BB_info = utils.get_basebox_info(image)
    base_box["mgmt_user"]=BB_info["mgmt_user"]
    
    if("mgmt_protocol" in BB_info):
        base_box["mgmt_protocol"]=BB_info["mgmt_protocol"]

    return base_box

def define_node(config, name, limits):
    node = dict()

    node["name"]=name
    node["flavor"]=config["flavor"]
    node["base_box"]=define_base_box(config["basebox"], limits)
    
    return node

def define_host(solution, name, limits):
    config = solution["hosts"][name]
    host = define_node(config, name, limits)

    if("disk" in config):
        disk = int(config["disk"])
        disk/=1_000_000_000
        #host["volumes"]=[{"size":disk}]
    return host

def define_router(solution, name, limits):
    config = solution["routers"][name]
    router = define_node(config, name, limits)
    return router

def define_network(solution, name):
    config = solution["networks"][name]
    network = dict()
    
    network["name"]=name
    network["cidr"]=config["netid"]
    if("accessible" in config):
        network["accessible_by_user"]=("true"==config["accessible"])
    return network

def map_nodes(solution, isHost):

    #extract relevant info
    mappings = list()
    node_type = "host" if isHost else "router"
    nodes = solution["hosts" if isHost else "routers"]
    networks = solution["networks"]

    #check every connection
    for network in networks:
        connected = networks[network]["connected"]
        for node in connected:

            #skip irrelevant connection
            ip = connected[node]
            if(not node in nodes):
                continue

            #add mapping
            mapping = dict()
            mapping[node_type]=node
            mapping["network"]=network
            mapping["ip"]=ip
            
            mappings.append(mapping)

            
    return mappings

def define_topology(solution):
    limits = utils.load_json("data/limits.json")

    #check for missing configuration segments
    if(not "networks" in solution):
        raise Exception("no networks present in solution")
    if(not "routers" in solution):
        raise Exception("no routers present in solution")
    if(not "hosts" in solution):
        raise Exception("no hosts present in solution")

    #map nodes to network
    host_mappings = map_nodes(solution, True)
    router_mappings = map_nodes(solution, False)

    #dynamically translated values
    networks=dict()
    routers=dict()
    hosts=dict()

    #static placeholder values
    name="generated-game"
    if("name" in solution):
        name=solution["name"]
    wan=dict({"name":"internet-connection","cidr":"100.100.100.0/24"})
    groups=[]

    #generate nodes and network
    for host_name in solution["hosts"]:
        hosts[host_name]=define_host(solution, host_name, limits)
            
    for router_name in solution["routers"]:
        routers[router_name]=define_router(solution, router_name, limits)
            
    for network_name in solution["networks"]:
        networks[network_name]=define_network(solution, network_name)

    #standardize nodes and networks
    networks = list(networks.values())
    routers = list(routers.values())
    hosts = list(hosts.values())

    #make topology
    topology = dict()
    topology["name"]=name
    
    topology["hosts"]=hosts
    topology["routers"]=routers
    topology["wan"]=wan
    topology["networks"]=networks
    
    topology["net_mappings"]=host_mappings
    topology["router_mappings"]=router_mappings
    topology["groups"]=groups

    return topology

def main(output_folder="output"):
    #read solution
    solution = utils.load_json("cache/solution.json")

    #generate topology definition
    topology = define_topology(solution)
    utils.save_file((output_folder, "topology.yml"), topology)
    
    #generate provisioning definition
    devices = utils.combine_dicts([solution["hosts"],solution["routers"]])
    prov.provision(output_folder, devices)
