import time
import scripts.stage1 as preprocessor
import scripts.stage2 as specifier
import scripts.stage3 as solver
import scripts.stage4 as translator
import sys
import traceback

silent_mode = False

def mutable_print(msg):
    if(not silent_mode):
        print(msg)
    return

debug_msg_length = 25

def run_stage(stage, input_file, output_folder, debug = True):
    t0 = time.time()

    #run corresponding stage
    try:
        if(stage=="preprocessor"):
            preprocessor.main(input_file)
        elif(stage=="specifier"):
            specifier.main()
        elif(stage=="solver"):
            solver.main()
        elif(stage=="translator"):
            translator.main(output_folder)
    except Exception:
        mutable_print(traceback.format_exc())
        return False

    #print time elapsed
    time_elapsed = time.time()-t0
    debug_msg = f'{stage} finished in'
    debug_msg+=" "*(debug_msg_length-len(debug_msg))
    
    if(debug):
        mutable_print(f'{debug_msg} {time_elapsed} s')
    return True
    

def main(args = dict()):

    #adapt to user arguements
    if(not "input" in args):
        args["input"]="input.vsdl"
    if(not "output" in args):
        args["output"]="output"
    if("--silent" in args["options"]):
        global silent_mode
        silent_mode = True

    #select required stages
    stages = ["preprocessor", "specifier", "solver", "translator"]
    if("stages" in args):
        start, end = args["stages"]
        
        start -= 1
        stages=stages[start:end]
        
    t0 = time.time()

    #run required stages
    for stage in stages:
        if(not run_stage(stage, args["input"], args["output"])):
            mutable_print(f"failed at stage: {stage} !")
            return 1


    debug_msg = f'total time elapsed:'
    debug_msg+=" "*(debug_msg_length-len(debug_msg))
    mutable_print(f'{debug_msg} {time.time()-t0}')
    return 0

if __name__ == "__main__":

    args = dict({"options":set()})
    allowed_options=dict({
        "-i":       "-i <input file>    : change input file, default is input.vsdl",
        "-o":       "-o <output folder> : change output folder, default is output/",
        "-stage":"-s <start>  |  -s <start:end>  : select stages to run",
        "--silent": "--silent : disables debugging print outs",
        "--help":   "--help   : prints out available options"
        })

    #extract arguements passed when initiating script
    prev_arg = None
    error_msgs = list()
    for arg in sys.argv:

        #specified input or output
        if(prev_arg == "-i"):
            args["input"]=arg
        elif(prev_arg == "-o"):
            args["output"]=arg

        #specified stages to run
        elif(prev_arg == "-stage"):
            interval = arg.split(':')
            start = interval[0]
            end = start if len(interval)==1 else interval[1]

            #use default values
            start = 1 if start=='' else int(start)
            end = 4 if end=='' else int(end)

            if(start>end):
                error_msgs.append("starting stage must preceed end stage")
            elif((not int(start) in range(1,5)) or (not int(end) in range(1,5))):
                error_msgs.append("specified stages must be within range <1,4>")

            args["stages"]=(start,end)

        #gather other options
        elif(not prev_arg is None):    
            args["options"].add(arg)
        prev_arg=arg

    #handle unrecognized options
    unrecognized_options = args["options"]-set(allowed_options.keys())
    if(len(unrecognized_options)!=0):
        print("unrecognized options, please use --help to list available options!")
        print("unrecognized options: ",unrecognized_options)

    #handle errors in recognized options
    elif(len(error_msgs)!=0):
        for error_msg in error_msgs:
            print(error_msg)

    #print manual
    elif("--help" in args["options"]):
        for option in allowed_options:
            print(allowed_options[option])
    else:   
        main(args)
    
