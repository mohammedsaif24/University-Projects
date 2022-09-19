//QUESTION 1:

MATCH (tweets: Tweet)
WHERE NOT (tweets)<-[:RETWEETOF]-() and  not (tweets)<-[:REPLYTO]-() 
and (not exists (tweets.replyto_id) and  not exists(tweets.retweet_id))
return count(tweets) AS NumberofTweets;

//=====================================================================================================
//QUESTION 2:

MATCH (tweets: Tweet)<-[:HASHTAGS]-(tags: Hashtag)
WHERE NOT EXISTS(tweets.retweet_id)
RETURN tags.name AS HashTags, count(*) AS hashtagCount 
ORDER BY hashtagCount 
DESC LIMIT 5;

//=====================================================================================================
//QUESTION 3:

MATCH (tweets: Tweet)
RETURN tweets.id AS Tweet_IDs, size((tweets)<-[:RETWEETOF|REPLYTO*1..]-()) AS countDescendents
ORDER BY countDescendents 
DESC LIMIT 1;

//=====================================================================================================
//QUESTION 4:

MATCH (tweets1: Tweet)<-[:RETWEETOF|REPLYTO*1..]-(tweets2: Tweet)
RETURN tweets1.id AS Tweet_ID, count(DISTINCT tweets2.user_id) AS countUserIDs
ORDER BY countUserIDs 
DESC LIMIT 1;

//=====================================================================================================
//QUESTION 5:

MATCH relation= (tweetVar1: Tweet)- [:RETWEETOF|REPLYTO*1..] -> (tweetVar2)
WITH REDUCE(listofNodes = [], t_id in nodes(relation) | listofNodes + t_id.id) AS requiredOutput
RETURN size(requiredOutput)-1 AS MaximumPathLength, REVERSE(requiredOutput) AS Tweet_IDs
ORDER BY MaximumPathLength
DESC LIMIT 1;

//=====================================================================================================
//QUESTION 6:


//=====================================================================================================

