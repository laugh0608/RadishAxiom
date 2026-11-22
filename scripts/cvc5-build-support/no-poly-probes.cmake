# This project describes only the two fixed CaDiCaL probes. It is reviewed as
# text until a later, separately authorized C3 build.
cmake_minimum_required(VERSION 3.25)
project(RadishAxiomCvc5NoPolyDependencyProbes C CXX)
include(CheckCXXSymbolExists)

check_cxx_symbol_exists(getc_unlocked "cstdio" HAVE_UNLOCKED_IO)
check_cxx_symbol_exists(closefrom "unistd.h" HAVE_CLOSEFROM)

foreach(name HAVE_UNLOCKED_IO HAVE_CLOSEFROM)
  if(${name})
    set(${name}_JSON true)
  else()
    set(${name}_JSON false)
  endif()
endforeach()
file(WRITE "${CMAKE_BINARY_DIR}/probe-results.json"
  "{\"format\":\"radishaxiom-private-cvc5-no-poly-dependency-probes\",\"version\":\"0.1\",\"unlocked_io\":${HAVE_UNLOCKED_IO_JSON},\"closefrom\":${HAVE_CLOSEFROM_JSON}}\n")
