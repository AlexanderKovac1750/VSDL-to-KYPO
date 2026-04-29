import json
import yaml
from pathlib import PurePath, Path

#this is first class created for this project, and it is purely cosmetic
#its only purpose is to standardize YAML output
#and ensure the indentation and new line follow same standard as KYPO example
class IndentDumper(yaml.Dumper):
    prev=0
    no_trivial = False
    
    def write_line_break(self, data=None):
        super().write_line_break(data)

        #add newline to top level list entries
        curr=len(self.indents)
        if( (curr==2 and self.prev!=1 or curr==1 and self.prev>1)):
            if(self.no_trivial or curr==1):
                super().write_line_break(data)
            self.no_trivial = False

        if(curr>2):
            self.no_trivial = True
        self.prev = curr  

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentDumper, self).increase_indent(flow, False)

## simple helper functions
def sort_dict(unsorted_dict):

    #recursively sort entries
    for entry in unsorted_dict:
        
        if(entry.__class__==tuple):
            raise Exception(f'dict_sort failed, "{entry}" is tuple !')
        if(unsorted_dict[entry].__class__==dict):
            unsorted_dict[entry]=sort_dict(unsorted_dict[entry])
        elif(unsorted_dict[entry].__class__==dict):
            unsorted_dict[entry]=sorted(unsorted_dict[entry])

    return dict(sorted(unsorted_dict.items()))

def combine_dicts(dictionaries):
    combined = dict()
    for single_dict in dictionaries:
        for entry in single_dict:
            combined[entry]=single_dict[entry]

    return combined

def concat(parts, sep=""):
    combined = ""
    first_part = True
    
    for part in parts:

        if(part=='' or part is None):
            continue

        if(not first_part):
            combined += sep

        combined += part
        first_part = False

    return combined

def safe_split(line):
    if(not '"' in line):
        return line.split()

    #get indices of quotes
    quote_separators = []
    was_commented = False
    
    for index, symbol in enumerate(line):
        if(not was_commented and symbol == '"'):
            quote_separators.append(index)
        was_commented = (symbol =='\\')

    #reshape indices list
    quote_indices = []
    for index in range(0,len(quote_separators),2):
        quote_indices.append(quote_separators[index:index+2])

    #extract words
    parts = []
    start = 0
    
    for quote in (quote_indices + [[]]):
        end = quote[0] if len(quote)==2 else len(line)

        #handle unqoted text
        words = line[start:end].split()
        parts += words
        start = end

        #handle quoted text
        if(end<len(line)):
            parts.append(line[quote[0]+1:quote[1]])
            start = quote[1]+1

    return parts

## STRING formatting functions
def encode_special_characters(attribute):

    encoded = ""
    for symbol in attribute:

        if(symbol.isalnum()):
            encoded+=symbol
        else:
            encoded+=f"@{ord(symbol)}$"

    return encoded

def decode_special_characters(attribute):
    if(not '@' in attribute):
        return attribute
    
    #decode special characters
    decoded = ""
    for strip in attribute.split('@'):
        parts = strip.split('$')
        
        if(len(parts)>=2):
            parts[0]=chr(int(parts[0]))

        decoded += concat(parts)

    return decoded

def pad(line, words):
    if(len(words)==0):
        raise Exception("no words specified!")

    #pad all specified words
    for word in words:
        line = line.replace(word, " "+word+" ")
    return line

## TERM helper functions
def check_naming_requirements(name):
    #check name requirements
    isalnum = name.replace('-','a').isalnum()
    if(isalnum):
        return True

    #find problematic characters
    index = 1
    while(index<=len(name)):

        if(not name[:index].replace('-','a').isalnum()):
            raise Exception(f'invalid name "{name}" -> symbol "{name[index-1]}" not allowed!')

        index+=1
        
def extract_terms(bigTerm):
    terms = set()
    
    if(bigTerm.__class__ != list and bigTerm.getNumChildren()==0):
        return set([bigTerm])

    for smallTerm in bigTerm:
        terms = set.union(terms, extract_terms(smallTerm))

    return terms

term_name_delimeter = '_'

def make_term_name(attribute, object_type, object_name):
    global term_name_delimeter
    delim = term_name_delimeter

    #format attribute name
    if(attribute.__class__ != tuple):
        attribute=[attribute]
    else:
        attribute=list(attribute)

    for attr_ind, attr_seg in enumerate(attribute):
        attribute[attr_ind]=encode_special_characters(attr_seg)
        
    attribute = concat(attribute,'.')
    
    #ensure term name remains breakable
    if(delim in attribute):
        raise Exception(f'the delim "{delim}" can\'t be present in attribute "{attribute}" !')
    if(delim in object_type):
        raise Exception(f'the delim "{delim}" can\'t be present in object_type "{object_type}" !')
    
    return f"{attribute}{delim}{object_type}{delim}{object_name}"

def break_term_name(term_name):
    global term_name_delimeter
    delim = term_name_delimeter

    #extract attribute name
    attr_end = term_name.find(delim)
    if(attr_end==-1):
        return term_name, None, None

    #format attribute name
    attribute = term_name[:attr_end]
    attr_segments = attribute.split('.')
    for attr_ind, attr_seg in enumerate(attr_segments):
        attr_segments[attr_ind]=decode_special_characters(attr_seg)

    #format to tuple or string
    attribute = tuple(attr_segments)
    if(len(attribute)==1):
        attribute=attribute[0]
    term_name = term_name[attr_end+1:]

    #extract object type
    object_type_end = term_name.find(delim)
    if(object_type_end==-1):
        return attribute, term_name, None
    
    object_type = term_name[:object_type_end]
    object_name = term_name[object_type_end+1:]

    return attribute, object_type, object_name

## IP parsing functions
def make_ip_str(ip_num, netsize = None):
    ip_str = ""
    sep = ""

    if(ip_num >= 2**32 or ip_num < 0):
        raise Exception("ip beyond IPv4 range!")
    
    for i in range(4):
        ip_str =  str(ip_num%256) + sep + ip_str
        sep = '.'
        ip_num //=256

    if(not netsize is None):
        mask = 32
        while(netsize>1):
            netsize//=2
            mask-=1

        ip_str+=f"/{mask}"
        
    return ip_str

def make_ip_num(ip_str, offset=None):

    #get octets
    octets = ip_str.split('.')
    if(len(octets)!= 4):
        raise Exception(f'expected IPv4 format, intead got "{ip_str}" !')

    #get number
    ip_num = 0
    for octet in octets:
        try:
            ip_num*=256
            ip_num += int(octet)
        except:
            raise Exception(f'when parsing ipv4 expected number, instead got "{octet}" !')

    #adjust granuality to get netid
    if(not offset is None):
        ip_num += offset
        ip_num -= ip_num % 2
        
    return ip_num


## SMT SET helper functions
def parse_set_syntax(set_string, numerical = False):

    #handle numerical sets
    if(numerical):
        nums = []
        for segment in set_string.split():
            stripped_segment = segment.rstrip(")")
            
            if(stripped_segment.isnumeric()):
                nums.append(int(stripped_segment))
        return nums
    
    #get raw items
    items=[]
    items_raw = set_string.split(' "')
    for item_raw in items_raw:

        #extract item names from set syntax
        item = item_raw.split('"')
        if(len(item)==2):
            items.append(item[0])

    return items
        
def build_set(entries, is_val, base = "(as set.empty (Set String))"):
    entries_str=""
    quotes = '"' if is_val else ""

    #no entries edge case
    if(len(entries)==0):
        return '(as set.empty (Set String))'
    
    for entry in entries:
        entries_str += quotes+ entry +quotes +" "
        
    return f'(set.insert {entries_str} {base})'

def populate_set(entries, is_val, set_name):
    populated_set = build_set(entries, is_val, set_name)
    return f'(assert(= {populated_set} {set_name}))'

## FILEPATH helper functions
def get_parent_path_str(path):
    path = Path(path)
    if(path.parent==path or path.parent==Path(".")):
        return None
    else:
        return path.parent.as_posix()

def standardize_path_str(path):
    standardized_path = PurePath(path).as_posix()
    
    if(standardized_path[0]=="/"):
        standardized_path=standardized_path[1:]
    return standardized_path

## FILE helper functions
def read_file(filename):
    file = open(filename, 'r')
    lines = file.readlines()
    
    file.close()
    return lines

def write_vsdl(file, data):
    scenario_name, objects = data
    file.write(f'scenario {scenario_name} {"{"}')
    
    for node_or_network in objects:
        file.write(f"\n{node_or_network} "+'{\n')

        for line in objects[node_or_network]:
            
            #add necessary quotes
            for index, word in enumerate(line):
                if(len(word.split())>1):
                    line[index] = f'"{word}"'
            
            file.write("\t"+concat(line,' ')+"\n")

        file.write("}\n")

    file.write("}")
    return

def write_smt(file, data):
    for group in data:
        file.write(f"\n;{group}\n")
        
        for line in data[group]:
            file.write(line+"\n")

def write_json(file, data):
    file.write(json.dumps(data, indent=4))

def load_json(filename):
    with open(filename, 'r') as file:
        data = json.load(file)

    file.close()
    return data

def write_yaml(file, data):
    file.write(yaml.dump(data, default_flow_style=False, sort_keys=False, Dumper=IndentDumper))

def load_yaml(filename):
    with open(filename, 'r') as file:
        data = yaml.load(file, Loader=yaml.SafeLoader)
        
    file.close()
    return data

def create_dir_recursively(dir_path):
    Path(dir_path).mkdir(parents=True, exist_ok = True)

def save_file(filename, data):

    #open file
    if(filename.__class__==tuple):
        filename = PurePath(filename[0], filename[1])
        create_dir_recursively(filename.parent)
        filename=str(filename)

    #save data
    file = open(filename, 'w')
    
    if(filename.endswith(".vsdl")):
        write_vsdl(file, data)    
    elif(filename.endswith(".smt") or filename.endswith(".smt2")):
        write_smt(file, data)
    elif(filename.endswith(".json")):
        write_json(file, data)
    elif(filename.endswith(".yaml") or filename.endswith(".yml")):
        write_yaml(file, data)
    else:
        file_format = filename.split('.')
        file_format = file_format[-1]
        file.close()
        raise Exception(f'unsupported format: "{file_format}"')
        
    file.close()
    
## basebox info - helper function
base_boxes = None
def get_basebox_info(base_box):
    
    #load baseboxes
    global base_boxes
    if(base_boxes is None):
        base_boxes = load_yaml("data/base_boxes.yml")

    #dont query, just load baseboxes
    if(base_box is None):
        return None

    #return basebox info
    if(not base_box in base_boxes):
        raise Exception(f'base box "{base_box}" not specified')
    return base_boxes[base_box]
    
