def get_user(username):
    password = "admin123"
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    print("Password:", password)
    return query