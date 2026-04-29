import scripts.utils as utils
import scripts.simple_statement_resolver as ssr
import scripts.enviromental_constraints as envc
import scripts.term_types as tt
import random

def format_implications(implications_raw):
    implications = list()
    
    #format implications
    for implication_raw in implications_raw:
        implication = f'(assert(=> {implication_raw} {implications_raw[implication_raw]}))'
        implications.append(implication)
    
    return implications

def check_for_expected_terms(networks, nodes, declared_terms):
    node_exp_attributes = tt.node_expected_terms
    for node in nodes:
        for exp_attr in node_exp_attributes:
            term = utils.make_term_name(exp_attr, "node", node)

            if(not term in declared_terms):
                raise Exception(f'missing {exp_attr} in node {node} !')

    network_exp_attributes = tt.network_expected_attributes
    for network in networks:
        for exp_attr in network_exp_attributes:
            term = utils.make_term_name(exp_attr, "network", network)

            if(not term in declared_terms):
                raise Exception(f'missing {exp_attr} in network {network} !')
    return

def resolve_statement(name, isNetwork, words, declared_terms, implications):
    #skip complex logic op analysis in case of simple
    if(not '(' in words):
        return ssr.resolve_simple_statement(name, isNetwork, words, declared_terms, implications)

    #statement analysis variables
    op = None
    sub_statements = list()
    ss_start = None
    index=0
    depth = 0
    
    #analyze statement
    for word in words:

        #keep track of depth
        if(word == "("):
            depth += 1
            if(depth == 1):
                ss_start = index
        elif(word==")"):
            depth -= 1
            
            #append sub statements
            if(depth == 0 and not ss_start is None):
                sub_statements.append(words[ss_start+1:index])

        #select op
        elif(depth==0):
            op = word

            if(not op in ["and","or","xor","not"]):
                raise Exception(f"unsupported logic operation {op} !")

        #track word index       
        index+=1

    #remove nonessential brackets
    if(op is None):
        return resolve_statement(name, isNetwork, words[1:len(words)-1], declared_terms, implications)

    #shuffle substatements order
    random.shuffle(sub_statements)

    #handle substatements
    sub_statements_str = ""
    for sub_statement in sub_statements:
        sub_statements_str += " "+resolve_statement(name, isNetwork,sub_statement, declared_terms, implications)
    
    return f"({op}{sub_statements_str})"

def generate_assert(name, isNetwork, words, declared_terms, implications):
    
    if(words.pop(len(words)-1)!=';'):#remove trailing ;
        raise Exception(f'missing ";" at the end of line {words} !')
    return f"(assert{resolve_statement(name,isNetwork, words, declared_terms, implications)})"

def get_terms_declarations(terms):
    declarations = list()
    for term in terms:
        term_type = ssr.get_term_type(term)
        declarations.append(f"(declare-const {term} {term_type})")
    return declarations

def generate_assertions(lines):

    object_name = None
    object_type = None
    implications = dict()
    assertions = list()
    declared_terms = set()
    networks = []
    nodes = []

    #process objects line by line
    for line in lines:
        words = utils.safe_split(line)

        #skip empty lines
        if(len(words)==0):
            continue

        #end of object segment
        if(words[0]=="}"):

            object_name = None
            object_type = None
            continue

        #start of object segment
        if(object_name is None and len(words)==3):
            object_name = words[1]
            object_type = words[0].lower()

            if(object_type=="network"):
                ssr.add_required_terms(object_name, True, declared_terms)
                networks.append(object_name)
            else:
                ssr.add_required_terms(object_name, False, declared_terms)
                nodes.append(object_name)
            continue

        #object statement
        if(object_name is not None):
            assertions.append(generate_assert(object_name, object_type=="network", words, declared_terms, implications))

    check_for_expected_terms(networks, nodes, declared_terms)
    return declared_terms, assertions, implications

def extract_scenario_name(lines):
    words = lines[0].split()
    if(len(words)!=3 or words[0]!="scenario"):
        return lines, "generated-game"
    
    scenario_name = words[1]
    return lines[1:-1], scenario_name

def assert_scenario_name(scenario_name, declared_terms, assertions):
    term=utils.make_term_name("scenario","name","general")
    declared_terms.add(term)
    
    statement_scenario = f'(assert(= "{scenario_name}" {term}))'
    assertions.append(statement_scenario)

def main():
    lines = utils.read_file("cache/preprocessed.vsdl")
    lines, scenario_name = extract_scenario_name(lines)
    
    declared_terms, assertions, implications = generate_assertions(lines)
    assert_scenario_name(scenario_name, declared_terms, assertions)
    terms_declaration = get_terms_declarations(declared_terms)

    implications = format_implications(implications)
    env_terms, env_constraints = envc.get_constraints(declared_terms)

    categories = ["node and network properties",
                  "assertions from user statements",
                  "statements implied by assertions",
                  "enviromental properties",
                  "environmental limits"]
    data = dict({
        categories[0]:terms_declaration,
        categories[1]:assertions,
        categories[2]:implications,
        categories[3]:env_terms,
        categories[4]:env_constraints
        })
    utils.save_file("cache/assertions.smt2", data)
