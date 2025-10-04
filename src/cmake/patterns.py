import re

enable_testing = re.compile(r'enable_testing\s*\(.*?\)', re.IGNORECASE | re.DOTALL)
include_ctest = re.compile(r'include\s*\(\s*CTest\s*\)', re.IGNORECASE | re.DOTALL)
add_test = re.compile(r'add_test\s*\(.*?\)', re.IGNORECASE | re.DOTALL)
discover_tests = re.compile(r'(gtest|catch|doctest)_discover_tests\s*\(.*?\)', re.IGNORECASE | re.DOTALL) 
target_link_libraries = re.compile(r'target_link_libraries\s*\([^)]*(gtest|Catch2|doctest)[^)]*\)', re.IGNORECASE | re.DOTALL)

