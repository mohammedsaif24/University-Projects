//Create Index
CREATE INDEX ON :Tweet(id);
CREATE INDEX ON :Hashtag(text);
CREATE INDEX ON :User(userid);


//Load the data
CALL apoc.load.json("file:///tweets.json")
YIELD value

//Set attributes for Tweet objects
MERGE (tweetObject: Tweet {id:value.id})
SET tweetObject.text = value.text,
tweetObject.created_at = value.created_at,
tweetObject.user_id = value.user_id,
tweetObject.retweet_id = value.retweet_id,
tweetObject.replyto_id = value.replyto_id,
tweetObject.retweet_user_id = value.retweet_user_id,
tweetObject.retweet_user_id = value.retweet_user_id,
tweetObject.replyto_user_id = value.replyto_user_id

//Create relationship between Tweet and User Mentions
FOREACH (umentions IN value.user_mentions |
		MERGE (user: User {userid: umentions.id})
		MERGE (user)-[:MENTIONEDIN]->(tweetObject)
		)

//Create relationship between Tweet and HashTags
FOREACH (htags IN value.hash_tags |
		MERGE (tag: Hashtag {name: htags.text})
		MERGE (tag)-[:HASHTAGS]->(tweetObject)
		)

//Create relationship between Tweet and Retweets
FOREACH (retweetID in
        CASE WHEN tweetObject.retweet_id IS NOT NULL
        THEN [tweetObject.retweet_id] ELSE [] END |
        MERGE (retweet_ParentObject: Tweet {id: retweetID}) 
		MERGE (tweetObject)-[:RETWEETOF]->(retweet_ParentObject))
		
//Create relationship between Tweet and Replies	
FOREACH (replyToID in
        CASE WHEN tweetObject.replyto_id IS NOT NULL
        THEN [tweetObject.replyto_id] ELSE [] END |
        MERGE (reply_ParentObject: Tweet {id: replyToID}) 
		MERGE (tweetObject)-[:REPLYTO]->(reply_ParentObject));