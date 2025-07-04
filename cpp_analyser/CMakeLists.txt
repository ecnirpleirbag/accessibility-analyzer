cmake_minimum_required(VERSION 3.10)
project(accessibility_cpp_analyser)
set(CMAKE_CXX_STANDARD 17)
add_executable(accessibility_cpp_analyser main.cpp pugixml.cpp)
# nlohmann_json is header-only, json.hpp should be in the same directory 