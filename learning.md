# db connection

- Engine - creates and manages connections, it also handles connection pooling like secuity guard of building(dictates how people enter, checks their credentials and decides how many people can be inside at once)
- Connection- takes raw SQL string(like SELECT*FROM users) drives it down pathway and executes it and bring back raw rows of data
- ORM- smart wrapper built on top of a connection, instead of dealing with raw sql strings, you deal with python objects

- SQLAlchemy (translates python to sql string)  -> The Driver(Converts to binary & ships via network protocols) -> PosgresSQL(execute query) -> The Driver(Converts binary back into python tuples/lists) -> SQLAlchemy(turns raw data into a nice python object)
