//drop graph
MATCH (n)
DETACH DELETE n;

//drop index
DROP INDEX ON :Tweet(id);
DROP INDEX ON :Hashtag(text);
DROP INDEX ON :User(userid);