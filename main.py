class Employee:
    def __init__(self, employee_id, name, email):
        self.employee_id = employee_id
        self.name = name
        self.email = email


employee_id = input("Enter employee ID: ")
employee_name = input("Enter employee name: ")
employee_email = input("Enter employee email: ")

employee = Employee(employee_id, employee_name, employee_email)

print()
print("Employee Created")
print("ID:", employee.employee_id)
print("Name:", employee.name)
print("Email:", employee.email)