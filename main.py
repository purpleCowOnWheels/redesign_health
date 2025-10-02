from generics import sha256_hash

linkedin_url = 'https://www.linkedin.com/in/daniel-sky-costanza/'
personId = sha256_hash(linkedin_url)
print(personId)