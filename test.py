import bcrypt

password = b"adminpassword"
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed.decode())
