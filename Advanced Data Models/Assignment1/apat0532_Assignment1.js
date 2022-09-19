/*
 * This script is for the Assignment 1 - MongoDB
 * 
 * This script assumes that you have imported the tweets data to a collection called tweets in a database a1.
*/

// make a connection to the database server
conn = new Mongo();

// set the default database
db = conn.getDB("a1");

db.tweets.aggregate(
[
    {
       $project: {
            _id: 1,
            id: 1,
            retweet_id: 1,
            replyto_id: 1,
            retweet_count: 1,
            hash_tags:1,
            created_at: {
                $dateFromString: {
                dateString: '$created_at',}
           }
       }
    },  
    {
       $out: 'tweets_v2',
    },
 ]);
 
 
//Creating index
db.tweets_v2.createIndex({id:1})
db.tweets_v2.createIndex({replyto_id:1})
db.tweets_v2.createIndex({retweet_id:1})

// timing the execution
var start = new Date()

//********************************************************************************************************************************

print("\nQUESTION 1: \n\n")
cursor = db.tweets_v2.aggregate([
    {
        $group: {
                _id: 0,
                "GeneralTweetsCount": {"$sum": {"$cond": [{"$and" : [{$not: ["$replyto_id"]}, {$not: ["$retweet_id"]}]}, 1, 0]}},
                "ReplyCount": {"$sum": {"$cond": [{$not: ["$replyto_id"]}, 0, 1]}},
                "RetweetCount": {"$sum": {"$cond": [{$not: ["$retweet_id"]}, 0, 1 ]}}
                }
    },
    {$project: {_id: 0, GeneralTweetsCount: 1, ReplyCount: 1, RetweetCount: 1}}
])

// display the result
while ( cursor.hasNext() ) {
    printjson( cursor.next());
}

//********************************************************************************************************************************

print("\nQUESTION 2: \n\n")

cursor = db.tweets_v2.aggregate([
    {$match: {$and: [{retweet_id : {$exists: false}}, {hash_tags: {$exists: true }}]}},
    {$unwind: "$hash_tags"},
    {$group: {_id: "$hash_tags.text", count: {$sum: 1}}},
    {$sort: {count :-1}},
    {$limit:5},
    
    {$project: {_id: 0, "HashTag": "$_id", "Count" : "$count"}}
])

// display the result
while ( cursor.hasNext() ) {
    printjson( cursor.next());
}

//********************************************************************************************************************************

print("\nQUESTION 3: \n\n")

cursor = db.tweets_v2.aggregate([
	{$lookup:
		{
			from:"tweets_v2",
			localField: "id",
			foreignField: "replyto_id",
			as: "ParentReply_Join"
		}
	},
	{$unwind : "$ParentReply_Join"},
	{$sort:{"ParentReply_Join.created_at" : 1}},
	{$group: {_id: {"id": "$id", "created_at": "$created_at"}, "ParentReply_Join": {$addToSet : "$ParentReply_Join"}}},   
	{$project:
				{   
					id : "$_id.id",
					MaximumTime: 
					{$divide : [{$subtract: [{$arrayElemAt:["$ParentReply_Join.created_at",0]}, "$_id.created_at"]}, 1000]}
				}
	},
	{$sort : {"MaximumTime":-1}},
	{$limit : 1},
	{$project: {_id:0, id: {$toString: "$_id.id"}, MaximumTime:1}}
])

// display the result
while ( cursor.hasNext() ) {
    printjson( cursor.next());
}

//********************************************************************************************************************************

print("\nQUESTION 4: \n\n")

cursor = db.tweets_v2.aggregate([
{$lookup: 
        {
            from: "tweets_v2",
            localField: "id" ,
            foreignField: "retweet_id",
            as: "ParentRetweet_Join"
        }
 },
{$match: {"$and": [{retweet_id:{$exists:false}}, {retweet_count:{$gt:0}}]}},
{$project: {_id:0, retweet_count:1, RetweetArraySize: {$size: "$ParentRetweet_Join"}}},
{$group: {_id:0 , TotalCount: {$sum:{$cond: [{$ne: ["$retweet_count", "$RetweetArraySize"]}, 1,0]}}}},
{$project: {_id:0, "Count of general and reply tweets that do not have all their retweets included in the data set": "$TotalCount"}}
])

while ( cursor.hasNext() ) {
    printjson( cursor.next());
}

//********************************************************************************************************************************

print("\nQUESTION 5: \n\n")

cursor = db.tweets_v2.aggregate([
{$lookup: 
        {
            from: "tweets_v2",
            localField: "retweet_id" ,
            foreignField: "id",
            as: "RetweetParent_Join"
        }
    },
{$lookup: 
        {
            from: "tweets_v2",
            localField: "replyto_id" ,
            foreignField: "id",
            as: "ReplyParent_Join"
        }
	},   
{$project: {retweet_id:1, replyto_id:1, RetweetParentArray_Size: {$size: "$RetweetParent_Join"}, ReplyParentArray_Size: {$size: "$ReplyParent_Join"}}
},
{$match: {$or: [{"replyto_id":{$exists:true}},{"retweet_id":{$exists:true}}]}},
{$match : {$and : [{"RetweetParentArray_Size":{$eq:0}},{"ReplyParentArray_Size":{$eq:0}}]}},
{$group : {_id: 0 , count : {$sum:1}}},
{$project: {_id: 0, "Count of tweets that do not have its parent tweet object in the data set": "$count"}}
])

while ( cursor.hasNext() ) {
    printjson( cursor.next());
}

//********************************************************************************************************************************

print("\nQUESTION 6: \n\n")

cursor = db.tweets_v2.aggregate([
{$lookup: 
        {
            from: "tweets_v2",
            localField: "id" ,
            foreignField: "retweet_id",
            as: "ParentRetweet_Join"
        }
    },
    
{$lookup: 
        {
            from: "tweets_v2",
            localField: "id" ,
            foreignField: "replyto_id",
            as: "ParentReply_Join"
        }
    },
	
{$project: {retweet_id: 1, replyto_id: 1, RetweetArraySize: {$size: "$ParentRetweet_Join"}, ReplyArraySize: {$size: "$ParentReply_Join"}}},
{$match: {$and: [{"replyto_id":{$exists:false}}, {"retweet_id":{$exists:false}}]}},
{$match: {$and : [{"RetweetArraySize":{$eq:0}}, {"ReplyArraySize":{$eq:0}}]}},
{$group: {_id: 0 , count : {$sum:1}}},
{$project: {_id: 0, "Count of general tweets that do not have a reply nor a retweet in the data set": "$count"}}
])

while ( cursor.hasNext() ) {
    printjson( cursor.next());
}

//********************************************************************************************************************************

var end = new Date()
print("\nQuery Execution time: " + (end - start) + "ms")

// drop the newly created collection
db.tweets_v2.drop()