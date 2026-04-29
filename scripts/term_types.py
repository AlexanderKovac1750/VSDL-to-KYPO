
#term categories
node_attributes = ["type", "flavor", "cpu", "disk", "OS", "memory",
                   "basebox"]
network_attributes = ["bandwidth"]

comparison_ops = {"equal to":"=",
                  "larger than":">",
                  "smaller than":"<",
                  "same as":"=",
                  "faster than":">",
                  "slower than":"<",
                  "at least":">=",
                  "at most":"<="}
valid_net_sizes = [4,8,16,32,64,128,256]+[2**i for i in range(9,33)]

#terms types
bool_terms = ["internet", "accessible", "permission."]
numeric_terms = ["netid", "netsize", "cpu", "disk", "memory", "bandwidth",
                 "forwards."]
numeric_set_terms = ["blocks."]
string_terms = ["connected.", "type", "flavor", "OS","basebox", "mounted.",
                "password.", "owner.", "scenario"]
string_set_terms = ["connected", "mounted", "files", "directories", "users",
                    "sudoers"]
specialized_terms = dict()

required_terms = ["OS", "basebox", "flavor", "disk", "memory"]
node_expected_terms = ["OS","basebox","flavor"]
network_expected_attributes = ["netid","netsize"]
