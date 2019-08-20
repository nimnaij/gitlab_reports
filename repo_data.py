

# if this is in an identifying field, it will be ignored and a different field is used.
anonymous_emails = ["user@station.local", "student", "you", "you@example.com", "noreply", "Your Name","noreply@github.com", "r", "root_ubuntu" , "ubuntu",  "bob","meh", "root",  "root@ubuntu" ]

#correlate user aliases to a single user.
known_aliases = {
  "ben" : [ "jianmin"],
}



known_namespaces = [ 'helpdesk']

# this manual lookup table provides
internal_external = {
 "ben": "internal"
 }



namespace_to_course = {}
namespace_to_course["helpdesk"] = "Organization Administration"
namespace_to_course["vta"] = "Infrastructure"
namespace_to_course["Module1"] = "Example Course"
namespace_to_course["Module2"] = "Example Course"
