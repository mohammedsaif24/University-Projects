/*
 * This is a sample script for MongoDB Assignment
 * It shows recommended practice and also basic steps
 * to connect to datanbase server, to set default database
 * and to drop a collection's working copy
 * 
 * The sample assumes that you have imported the tweets data
 * to a collection called tweets in a database a1.
*/

// make a connection to the database server
conn = new Mongo();

// set the default database
db = conn.getDB("a1");

// duplicate the tweets collection and update the created_at type
// the new collection name is tweets_v2
// aggregation pipe line is used to avoid transferring the entire
// collection to the client side

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

// you can add index to your new collection

// optionally timing the execution
var start = new Date()

// Creating indexes
db.tweets_v2.createIndex({id:1})
db.tweets_v2.createIndex({replyto_id:1})
db.tweets_v2.createIndex({retweet_id:1})

//Q1
print("Q1=============================================")
cursor1 = db.tweets_v2.aggregate(
	[{
            $facet:{
                "general_tweets" : [
                    {$match:{ replyto_id : {$exists : false},retweet_id : {$exists : false} }},
                    {$group : {_id : "user_id", "count_general" : {$sum : 1}}},
					{$project : {count_general : 1, _id : 0} }
                    
                    
                ],
                "reply_tweets" : [
                    {$match:{ replyto_id : {$exists : true},retweet_id : {$exists : false} }},
                    {$group : {_id : "user_id", "count_reply" : {$sum : 1}}},
					{$project : {count_reply : 1, _id : 0} }
                    
                ],
                "retweets" : [
                    {$match:{ replyto_id : {$exists : false},retweet_id : {$exists : true} }},
                    {$group : {_id : "user_id", "count_retweet" : {$sum : 1}}},
					{$project : {count_retweet : 1, _id : 0} }
                    
                ],
            }
        



    }]
)

while ( cursor1.hasNext() ) {
    printjson( cursor1.next() );
}


//Q2
print("\nQ2=============================================")
cursor2 = db.tweets_v2.aggregate(
    [
        {$match: {"hash_tags" : {"$exists" : true}}},
        {$match:
                {$and : [
                    {$or:[
                        {"replyto_id" : {"$exists" : false},retweet_id : {"$exists" : false} },
                        {"replyto_id" : {"$exists" : true},retweet_id : {"$exists" : false} },
            
                        ]}
                ]},
        },
        
        {$unwind: "$hash_tags" },
        {$group:{_id: '$hash_tags.text', count_hashtags: {$sum:1}}},
        {$sort:{count_hashtags:-1}},
        {$limit:5}

    ]
)

while ( cursor2.hasNext() ) {
    printjson( cursor2.next() );
}


//Q3
print("\nQ3=============================================")
cursor3 = db.tweets_v2.aggregate(
    [
        {$match: { replyto_id : {$exists : true},retweet_id : {$exists : false} }},
        {$lookup:
            {
                from: "tweets_v2",
                localField: "id",
                foreignField: "replyto_id",
                as: "replyTweetID"
            }
        },
        
        {$project:
            {
                id : "$id",
                interval: 
                {
                    $subtract:
                    [
                        {$arrayElemAt:["$replyTweetID.created_at",0]},
                        "$created_at"
                        
                    ]
                },
                
            }
        },
        {$sort:{interval:-1}},
        {$limit:1},
		{$project:
            {
                _id : 0,                
				id : {$toString: "$id"},
                duration: 
                {
                    $divide:
                    [
                        "$interval",1000
                        
                    ]
                },
                
            }
        },
       
    ]
)

while ( cursor3.hasNext() ) {
    printjson( cursor3.next() );
}



//Q4
print("\nQ4=============================================")
cursor4 = db.tweets_v2.aggregate(
    [
        {$match: {"retweet_count" : {"$gte" : 1}}},
        {$match:
                {$and : [
                    {$or:[
                        {"replyto_id" : {"$exists" : false},retweet_id : {"$exists" : false} },
                        {"replyto_id" : {"$exists" : true},retweet_id : {"$exists" : false} },
            
                        ]}
                ]},
        },

        {$lookup:
            {
                from: "tweets_v2",
                localField: "id",
                foreignField: "retweet_id",
                as: "ReTweetedID"
            }
        },
        {$project : 
            {retweet_Array_Size : {$size : "$ReTweetedID",}, retweet_count : 1 
            },
            },
        {$project : {cmpSizes : {$cmp : ["$retweet_count","$retweet_Array_Size" ]}, 
            retweet_count : 1,
            retweet_Array_Size : 1
            }},
         {$match : {"cmpSizes" : 1} },  
         {$group : {_id : null, "final_count" : {$sum : 1} }},
		 {$project :{_id : 0}}

        
    ]
)

while ( cursor4.hasNext() ) {
    printjson( cursor4.next() );
}



//Q5
print("\nQ5=============================================")
cursor5 = db.tweets_v2.aggregate(
    [
        {$match:
                {$and : [
                    {$or:[
                        {"replyto_id" : {"$exists" : false},retweet_id : {"$exists" : true} },
                        {"replyto_id" : {"$exists" : true},retweet_id : {"$exists" : false} },
            
                        ]}
                ]},
         },
         
         {$lookup:
            {
                from: "tweets_v2",
                localField: "retweet_id",
                foreignField: "id",
                as: "retweetParentID"
            }
         },
         {$lookup:
            {
                from: "tweets_v2",
                localField: "replyto_id",
                foreignField: "id",
                as: "replyParentID"
            }
         }, 
         {$project : 
            {retweet_Array_Size : {$size : "$retweetParentID",}, 
                reply_Array_Size : {$size : "$replyParentID",}
            },
            },
         {$match:{ retweet_Array_Size : 0, reply_Array_Size : 0 }}, 
         {$group : {_id : null, "final_count" : {$sum : 1} }},
         {$project :{_id : 0}}
        

    ]
)


while ( cursor5.hasNext() ) {
    printjson( cursor5.next() );
}




//Q6
print("\nQ6=============================================")
cursor6 = db.tweets_v2.aggregate(
    [
        {$match:{ replyto_id : {$exists : false},retweet_id : {$exists : false} }},
        
        {$lookup:
            {
                from: "tweets_v2",
                localField: "id",
                foreignField: "retweet_id",
                as: "ReTweetedID"
            }
         },
         {$lookup:
            {
                from: "tweets_v2",
                localField: "id",
                foreignField: "replyto_id",
                as: "ReplyID"
            }
         }, 
         {$project : 
            {retweet_Array_Size : {$size : "$ReTweetedID",}, 
                reply_Array_Size : {$size : "$ReplyID",}
            },
            },
         {$match:{ retweet_Array_Size : 0, reply_Array_Size : 0 }}, 
         {$group : {_id : null, "final_count" : {$sum : 1} }},
		 {$project :{_id : 0}}
            
            
    ]
)

while ( cursor6.hasNext() ) {
    printjson( cursor6.next() );
}



var end = new Date()
print("\nQuery Execution time: " + (end - start) + "ms")
// drop the newly created collection
db.tweets_v2.drop()