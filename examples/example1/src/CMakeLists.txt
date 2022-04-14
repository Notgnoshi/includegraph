file(GLOB_RECURSE sources CONFIGURE_DEPENDS "*.cpp")

target_sources(example1 PRIVATE ${sources})
unset(sources)

file(GLOB_RECURSE headers CONFIGURE_DEPENDS ".h")
target_sources(example1 PRIVATE ${headers})
unset(headers)
