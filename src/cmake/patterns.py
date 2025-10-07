import re

enable_testing = re.compile(r'enable_testing\s*\(.*?\)', re.IGNORECASE | re.DOTALL)
include_ctest = re.compile(r'include\s*\(\s*CTest\s*\)', re.IGNORECASE | re.DOTALL)
add_test = re.compile(r'add_test\s*\(.*?\)', re.IGNORECASE | re.DOTALL)
discover_tests = re.compile(r'(gtest|catch|doctest)_discover_tests\s*\(.*?\)', re.IGNORECASE | re.DOTALL) 
target_link_libraries = re.compile(r'target_link_libraries\s*\([^)]*(gtest|Catch2|doctest)[^)]*\)', re.IGNORECASE | re.DOTALL)
# TODO
add_test_exec = re.compile(r'add_test\s*\(.*?\)', re.IGNORECASE | re.DOTALL)

gtest_link = re.compile(r'target_link_libraries\s*\([^)]*(gtest)[^)]*\)', re.IGNORECASE | re.DOTALL)
catch_link = re.compile(r'target_link_libraries\s*\([^)]*(Catch2)[^)]*\)', re.IGNORECASE | re.DOTALL)
doctest_link = re.compile(r'target_link_libraries\s*\([^)]*(doctest)[^)]*\)', re.IGNORECASE | re.DOTALL)