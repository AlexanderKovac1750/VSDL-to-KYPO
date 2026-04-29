import scripts.utils as utils
import scripts.software_versioning as sv

def handle_base_boxes(allowed, terms, constraints, constraint_terms):
    
    #Base box constraints
    set_name = utils.make_term_name("BaseBoxes", "limit", "allowed")
            
    constraint_terms.append(f'(declare-const {set_name} (Set String))')
    constraints.append(f'(assert(= (set.card {set_name}) {len(allowed)}))')
    constraints.append(utils.populate_set(allowed, True, set_name))
    constraints.append(utils.populate_set(terms["basebox"], False, set_name))

    #OS constraints
    # allowed selection for OS is implicitely handled by basebox allowed selection

    #handle base box selection
    constraint_terms.append("(declare-fun OS_getter (String) String)")
    for base_box in allowed:

        #get versioned OS
        os_name = utils.get_basebox_info(base_box)["OS"]
        os_name, version = sv.extract_software_version(os_name)

        #encode version
        if(not version is None):
            os_name += "-" + sv.encode_version(version)
        
        constraints.append(f'(assert(= "{os_name}" (OS_getter "{base_box}")))')

    if(len(terms["basebox"]) != len(terms["OS"])):
        raise Exception("OS and basebox terms are not perfectly mapped!")

    for base_box in terms["basebox"]:
        os_term = "OS"+base_box.lstrip("basebox")
        constraints.append(f'(assert(= {os_term} (OS_getter {base_box})))')

def handle_flavors(allowed, terms, constraints, constraint_terms):

    #flavor contraints
    set_name = utils.make_term_name("flavor", "limit", "allowed")
    constraint_terms.append(f'(declare-const {set_name} (Set String))')
    constraints.append(f'(assert(= (set.card {set_name}) {len(allowed)}))')
    
    constraints.append(utils.populate_set(allowed, True, set_name))
    constraints.append(utils.populate_set(terms["flavor"], False, set_name))

    #memory contraints
    if("memory" in terms):
        constraint_terms.append("(declare-fun memory_getter (String) Int)")
        for flavor in allowed:
            memory = allowed[flavor]["RAM"]
            constraints.append(f'(assert(= {memory} (memory_getter "{flavor}")))')

        memory_terms = set(terms["memory"])
        for memory_term in memory_terms:
            flavor_term = "flavor"+memory_term.lstrip("memory")
            constraints.append(f'(assert(= {memory_term} (memory_getter {flavor_term})))')

    #disk contraints
    if("disk" in terms):
        constraint_terms.append("(declare-fun disk_getter (String) Int)")
        for flavor in allowed:
            disk = allowed[flavor]["disk"]
            constraints.append(f'(assert(= {disk} (disk_getter "{flavor}")))')

        disk_terms = set(terms["disk"])
        for disk_term in disk_terms:
            flavor_term = "flavor"+disk_term.lstrip("disk")
            constraints.append(f'(assert(= {disk_term} (disk_getter {flavor_term})))')
    
    return

def seperate_terms_by_attribute(declared_terms):
    terms = dict()

    for declared_term in declared_terms:
        attribute, object_type, object_name = utils.break_term_name(declared_term)

        if(attribute.__class__ == tuple):
            attribute = attribute[0]+'.'

        if(not attribute in terms):
            terms[attribute]=[]

        terms[attribute].append(declared_term)

    return terms

def get_constraints(declared_terms):
    limits = utils.load_json("data/limits.json")
    terms = seperate_terms_by_attribute(declared_terms)

    constraint_terms = []
    constraints = []

    for limit in limits:
        
        #handle base_boxes
        if(limit=="base_boxes" and "allowed" in limits[limit] and "OS" in terms):
            handle_base_boxes(limits[limit]["allowed"], terms, constraints, constraint_terms)
            continue

        #handle flavors
        if(limit=="flavors" and "allowed" in limits[limit]):
            handle_flavors(limits[limit]["allowed"], terms, constraints, constraint_terms)
            continue

        #skip unused
        if(not limit in terms):
            continue
        ops = limits[limit]

        #individual min max constraint
        limit_min = ops["individual.min"] if "individual.min" in ops else ""
        limit_max = ops["individual.max"] if "individual.max" in ops else ""

        if(limit_min != "" or limit_max != ""):
            for term in terms[limit]:
                constraints.append(f"(assert(<= {limit_min} {term} {limit_max}))")

        #total min max constraint
        limit_min = ops["total.min"] if "total.min" in ops else ""
        limit_max = ops["total.max"] if "total.max" in ops else ""

        if(limit_min != "" or limit_max != ""):
            total = utils.concat(terms[limit]," ")
            constraints.append(f"(assert(<= {limit_min} (+ 0 {total}) {limit_max}))")
            
        #allowed members
        if("allowed" in ops):
            allowed = ops["allowed"]
            set_name = utils.make_term_name(limit, "limit", "allowed")
            
            constraint_terms.append(f'(declare-const {set_name} (Set String))')
            constraints.append(f'(assert(= (set.card {set_name}) {len(allowed)}))')

            constraints.append(utils.populate_set(allowed, True, set_name))
            constraints.append(utils.populate_set(terms[limit], False, set_name))

    #verify version syntax
    for term in terms["mounted."] if "mounted." in terms else []:

        attr, object_type, device = utils.break_term_name(term)
        mounted_term = utils.make_term_name("mounted", object_type, device)

        #get software and versions
        software = attr[1]
        versions = sv.get_versions(software)

        #encode versions
        encoded_versions = []
        for version in versions:
            encoded_versions.append(sv.encode_version(version))
        
        software_versions = utils.build_set(encoded_versions, True)
        constraints.append(f'(assert(=> (set.member "{software}" {mounted_term}) (set.member {term} {software_versions})))')

        #add version statements
        for version in versions:
            version_req = sv.get_version_requirements(device, software, version)
            
            if(not version_req is None):
                constraints.append(f'(assert {version_req})')
            
    return constraint_terms, constraints


        

        
