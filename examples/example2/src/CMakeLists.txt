file(GLOB_RECURSE sources CONFIGURE_DEPENDS "*.cpp")

target_sources(example2 PRIVATE ${sources})
unset(sources)

file(GLOB_RECURSE headers CONFIGURE_DEPENDS ".h")
target_sources(example2 PRIVATE ${headers})
unset(headers)
