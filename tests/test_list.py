"""
Test: Variable scoping with integers vs lists
Demonstrate the difference between assignment and modification
"""

print("="*70)
print("Part 1: Integer Variable")
print("="*70)

count_int = 0  # Global integer

def test_int_1():
    """Read global integer"""
    print(count_int)  # ✅ Reading global, success

def test_int_2():
    """Assignment creates local variable"""
    count_int = 5  # ❌ Assignment → creates local variable
    print(count_int)  # Print out 5 (local variable)

def test_int_3():
    """Assignment without initialization fails"""
    try:
        count_int += 1  # ❌ Assignment → creates local, but not defined, fail
    except UnboundLocalError as e:
        print(f"Error: {e}")

def test_int_4():
    """Use global keyword to modify"""
    global count_int
    count_int += 1  # ✅ Use global, change it

# Run integer tests
print("\nTest 1: Read global integer")
test_int_1()

print("\nTest 2: Assignment creates local variable")
test_int_2()
print(f"Global count_int after test2: {count_int}")  # Still 0

print("\nTest 3: Assignment fails without initialization")
test_int_3()

print("\nTest 4: Use global keyword")
test_int_4()
print(f"Global count_int after test4: {count_int}")  # Now 1

print("\n" + "="*70)
print("Part 2: List Variable")
print("="*70)

count_list = [0]  # Global list

def test_list_1():
    """Read global list"""
    print(count_list)  # ✅ Reading global, success

def test_list_2():
    """Assignment creates local variable"""
    count_list = [999]  # ❌ Assignment → creates local variable
    print(count_list)  # Print out [999] (local)

def test_list_3():
    """Modify content without assignment"""
    count_list[0] += 1  # ✅ Modify content, not assignment, success

def test_list_4():
    """Use global keyword to reassign"""
    global count_list
    count_list = [999]  # ✅ Use global keyword
    print(count_list)

# Run list tests
print("\nTest 1: Read global list")
test_list_1()

print("\nTest 2: Assignment creates local variable")
test_list_2()
print(f"Global count_list after test2: {count_list}")  # Still [0]

print("\nTest 3: Modify content (no assignment)")
test_list_3()
print(f"Global count_list after test3: {count_list}")  # Now [1]

print("\nTest 4: Use global keyword to reassign")
test_list_4()
print(f"Global count_list after test4: {count_list}")  # Now [999]

print("\n" + "="*70)
print("Summary")
print("="*70)
print("""
Key Points:

1. Integer (immutable):
   - Read: ✅ Can access global
   - Modify: ❌ Cannot modify without 'global' keyword
   - Assignment: Creates local variable (unless 'global' used)

2. List (mutable):
   - Read: ✅ Can access global
   - Modify content: ✅ Can modify without 'global' (e.g., list[0] = x)
   - Reassign: ❌ Creates local variable (unless 'global' used)

3. Rule:
   - If you ASSIGN to a variable name (var = ...)
     → Python treats it as LOCAL
   - If you only READ or MODIFY CONTENT (var[0] = ...)
     → Python uses GLOBAL (if exists)

4. Why list trick works in callbacks:
   - count[0] += 1  → Modifies content, not assignment to 'count'
   - count = [1]    → Assignment, creates local variable
""")
