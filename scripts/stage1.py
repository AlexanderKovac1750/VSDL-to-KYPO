import scripts.utils as utils
import scripts.term_types as tt
import scripts.vulnerability_injector as vi
import copy
import sys

def format_units(bracketed_objects):
    comp_ops = dict()

    #generate set of available comparisons
    for comp_op in tt.comparison_ops:
        words = comp_op.split(" ")
        
        if(len(words)!=2 or words[0]=="same"):
            continue
        
        elif(not words[0] in comp_ops):
            comp_ops[words[0]]=set()
            
        comp_ops[words[0]].add(words[1])

    #go over every preprocessed statement word by word
    for entry in bracketed_objects:
        for statement in bracketed_objects[entry]:

            word_pos = 0
            chosen_comp = None
            i = -1

            
            while i < len(statement)-1:
                i+=1
                word = statement[i]

                #<attribute>
                if(word_pos==0 and word in tt.numeric_terms):
                    word_pos=1
                    continue

                #is
                elif(word_pos==1 and word == "is"):
                    word_pos=2
                    continue

                #<comp_1>
                elif(word_pos==2 and word in comp_ops):
                    chosen_comp = comp_ops[word]
                    word_pos=3
                    continue

                #<comp_2> 
                elif(word_pos==3 and word in chosen_comp):
                    word_pos=4
                    continue

                #value [unit]
                elif(word_pos==4 and not word.isnumeric()):
                    digits = "0123456789"
                    unit = word.lstrip(digits).lstrip(".").lstrip(digits)

                    #add space between value and unit
                    statement[i]=statement[i].rstrip(unit)
                    statement.insert(i+1, unit)

                #reset
                word_pos=0
                comp = None
                    
    return bracketed_objects
    

def add_bracket_L(words, index, op, stopmarks):
    tail_index = index
    depth = 0
    correctly_bracketed = words[tail_index-1]==")"

    index-=1
    while(index>=0):
        
        #outside of scope
        if(depth<0):
            break
        
        if(words[index]==')'):
            depth+=1
            index-=1
            continue
        
        elif(words[index]=='('):
            depth-=1
            index-=1
            continue

        
        if(depth==0):
                
            if(words[index] in stopmarks+[op]):
                break
            if(correctly_bracketed):
                correctly_bracketed = False
        index-=1

    if(correctly_bracketed):
        return

    words.insert(tail_index, ')')
    words.insert(index+1, '(')
    
def add_bracket_R(words, index, op, stopmarks):
    head_index = index + 1
    depth = 0
    correctly_bracketed = words[head_index]=="("

    index+=1
    while(index<len(words) and words[index]!=';'):

        #outside of scope
        if(depth<0):
            break
        
        if(words[index]=='('):
            depth+=1
            index+=1
            continue
        
        elif(words[index]==')'):
            depth-=1
            index+=1
            continue
        
        if(depth==0):
                
            if(words[index] in stopmarks+[op]):
                break
            if(correctly_bracketed):
                correctly_bracketed = False
        index+=1

    if(correctly_bracketed):
        return

    words.insert(head_index, '(')
    words.insert(index+1, ')')

def add_brackets_to_statement(words, op, other_ops = [], right_only = False):
    if(not op in words):
        return 0

    #add brackets to the operands
    i = -1
    while(i<len(words)-1):
        i+=1
        
        if(words[i] == op):
            add_bracket_R(words, i, op, other_ops)
            if(right_only):
                continue
            add_bracket_L(words, i, op, other_ops)

def add_logic_ops_scopes(objects):
    prepprocessed_objects = copy.deepcopy(objects)

    #enclose the sub statements in brackets
    for entry in prepprocessed_objects:
        for statement in prepprocessed_objects[entry]:
            add_brackets_to_statement(statement, "not", ["and","xor","or"], True)
            add_brackets_to_statement(statement, "and", ["xor","or"])
            add_brackets_to_statement(statement, "xor", ["or"])
            add_brackets_to_statement(statement, "or")
    
    return prepprocessed_objects

def extract_objects(lines):
    objects = dict()
    depth = 0
    current_object = None
    current_assertion = list()
    line_index = 0

    #read line by line
    for line in lines:
        line = utils.pad(line, ['{', '}', ';', '(', ')'])
        line = line.rstrip("\n")

        #break line to words
        words = utils.safe_split(line)
        line_index+=1

        #skip empty or comment lines
        if(len(words) == 0 or words[0].startswith("//")):
            continue

        #obtain object_name
        if(depth == 0):
            if(len(words)<2):
                raise Exception(f'expected object name, instead got "{line}" on line {line_index}!')

            #handle duplicit objects
            object_name = words[1]
            if(object_name in objects):
                raise Exception(f"duplicit object name {object_name} on line {line_index}!")

            #verify name validity
            utils.check_naming_requirements(object_name)

            #prepare to process the object 
            current_object = words[0] + " " + object_name
            objects[current_object]=list()

            if(len(current_assertion)!=0):
                raise Exception(f'unfinished statement "{current_assertion}" !')
            current_assertion.clear()

        #go over every word
        for word in words:

            #end of object constraints
            if(word=='}'):
                depth-=1

            #handle statements
            if(depth>0):
                current_assertion.append(word)

                #end of assertion
                if(word == ';'):
                    objects[current_object].append(copy.copy(current_assertion))
                    current_assertion.clear()

            #start of object constraints
            if(word=='{'):
                depth+=1
        
    #return extracted objects in dictionary
    if(len(current_assertion)!=0):
        raise Exception(f'unfinished statement "{current_assertion}" !')
    if(depth != 0):
        raise Exception(f'invalid scope, {abs(depth)} missing "{"{" if depth<0 else "}"}" !')
    if(len(objects)==0):
        raise Exception("no nodes or network present in input file!")
    return objects

def extract_scenario_name(lines):
    
    scenario_name = "generated-game"
    scenario_specified = False

    #find start of scenario statement
    for index, line in enumerate(lines):
        words = line.split()
        
        if(len(words)==0):
            continue

        #extract the scenario name
        if(words[0]=="scenario" and len(words)>=2):
            scenario_name=words[1]
            scenario_name=scenario_name.rstrip().rstrip("{")
            
            utils.check_naming_requirements(scenario_name)
            lines[index]=""
            scenario_specified= True
            
        break

    #use default scenario name if none is specified
    if(not scenario_specified):
        return lines, scenario_name

    for index in range(len(lines)-1,0,-1):
        end = lines[index].rfind("}")

        if(end!=-1):
            lines[index]=lines[index][:end]
            break

    return lines, scenario_name 

def main(filename = "input.vsdl"):
    
    lines = utils.read_file(filename)
    lines, scenario_name = extract_scenario_name(lines)
    objects = extract_objects(lines)
    
    correctly_bracketed = add_logic_ops_scopes(objects)
    preprocessed_objects = format_units(correctly_bracketed)
    vi.expand_suffer_statements(preprocessed_objects)

    utils.save_file("cache/preprocessed.vsdl", (scenario_name, preprocessed_objects))
