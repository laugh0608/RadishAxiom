# Self-authored capability probe project; only staged as text in C2.
# Running CMake here compiles detection programs and needs separate authorization.
cmake_minimum_required(VERSION 3.25)
project(RadishAxiomCvc5DependencyProbes C CXX)
include(CheckSymbolExists)
include(CheckCXXCompilerFlag)

# Preserve the headers and conditional macros from the pinned FindCaDiCaL.
check_symbol_exists(getc_unlocked "cstdio" HAVE_UNLOCKED_IO)
check_symbol_exists(closefrom "fcntl.h" HAVE_CLOSEFROM)
check_cxx_compiler_flag(-Wno-error=deprecated-literal-operator
  HAVE_DEPRECATED_LITERAL_FLAG)

foreach(name HAVE_UNLOCKED_IO HAVE_CLOSEFROM HAVE_DEPRECATED_LITERAL_FLAG)
  if(${name})
    set(${name}_JSON true)
  else()
    set(${name}_JSON false)
  endif()
endforeach()
file(WRITE "${CMAKE_BINARY_DIR}/probe-results.json"
  "{\"format\":\"radishaxiom-private-cvc5-dependency-probes\",\"version\":\"0.1\",\"unlocked_io\":${HAVE_UNLOCKED_IO_JSON},\"closefrom\":${HAVE_CLOSEFROM_JSON},\"deprecated_literal_flag\":${HAVE_DEPRECATED_LITERAL_FLAG_JSON}}\n")
