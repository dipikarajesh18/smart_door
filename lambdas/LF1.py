import json
import sys
sys.path.insert(1, '/opt')
import cv2
import boto3
import base64
from botocore.vendored import requests
from boto3.dynamodb.conditions import Key, Attr
import random
import time
import math

def append_to_visitors(faceId):
    # Find the item with given faceId.
    dynamo_client = boto3.resource('dynamodb')
    visitors_table = dynamo_client.Table('visitors');
    response = visitors_table.query(KeyConditionExpression=Key('faceID').eq(faceId))
    name = response['Items'][0]['name']
    # Create obj key and transfer frame.jpg to this with the given obj key.
    createdTimeStamp = int(time.time())
    objKey = name + str(createdTimeStamp) + ".jpg"
    copy_to_photos_bucket(objKey)
    # Add obj key to the visitors table.
    result = visitors_table.update_item(
        Key={
            'faceID': faceId
        },
        UpdateExpression="SET photos = list_append(photos, :i)",
        ExpressionAttributeValues={
            ':i': [{'objectKey':objKey, 'bucket':'rekognition-photos', 'createdTimeStamp':createdTimeStamp}],
        },
        ReturnValues="UPDATED_NEW"
    )
    if result['ResponseMetadata']['HTTPStatusCode'] == 200 and 'Attributes' in result:
        return result['Attributes']['photos']
    else:
        return "Did not insert"
def copy_to_photos_bucket(objKey):
    s3 = boto3.resource('s3')
    copy_source = {
      'Bucket': 'rekframebucket',
      'Key': "frame.jpg"
    }
    photoname = objKey
    visitors_photos = s3.Bucket('rekognition-photos')
    visitors_photos.copy(copy_source, photoname, {'ACL' : 'public-read'})
	
def generateOTP() : 
    digits = "0123456789"
    OTP = "" 
    for i in range(6) : 
        OTP += digits[math.floor(random.random() * 10)] 
    return OTP
    
def getPhone(faceId) :
    dynamo_client = boto3.resource('dynamodb')
    visitors_table = dynamo_client.Table('visitors');
    response = visitors_table.query(KeyConditionExpression=Key('faceID').eq(faceId))
    print("This is the phone number response : ",response)
    phoneNum = response['Items'][0]['phoneNumber']
    return phoneNum

def insert_into_passcodes(otp, faceId):
    dynamo_client = boto3.resource('dynamodb')
    otp_table = dynamo_client.Table('passcodes')
    exists = otp_table.query(IndexName='faceId-index', KeyConditionExpression=Key('faceId').eq(faceId))
    if len(exists['Items'])!=0:
        return False;
    otp_table.put_item(
        Item={
            "ID": str(time.time()),
            "faceId" : faceId,
            "otp" : otp,
            "ttl" : int(time.time() + 300)
            }
    )
    return True;
    
def send_otp(otp, faceId):
    number = getPhone(faceId)
    print("This is the phone number : ",number)
    sns = boto3.client("sns")
    msg = "Your One Time Password is " + str(otp) + " Enter it in this link.  " + "http://virtual-door-files.s3-website-us-west-2.amazonaws.com/otp_validate/"
    sub = "Your Smart Gate OTP"
    response = sns.publish(PhoneNumber=number, Message=msg,Subject=sub) 
    print("SMS sent" + json.dumps(response))

def lambda_handler(event, context):
    # TODO implement
    kvs_client = boto3.client('kinesisvideo',region_name='us-west-2')
    kvs_data_pt = kvs_client.get_data_endpoint(
        StreamARN='arn:aws:kinesisvideo:us-west-2:632033863834:stream/LiveRekognitionVideoAnalysisBlog/1586205325374', # kinesis stream arn
        APIName='GET_MEDIA'
    )
    
    print(kvs_data_pt)
    
    end_pt = kvs_data_pt['DataEndpoint']
    kvs_video_client = boto3.client('kinesis-video-media', endpoint_url=end_pt, region_name='us-west-2') # provide your region
    print("Records : ", event['Records'])
    record = event['Records'][0]
    payload = base64.b64decode(record["kinesis"]["data"])
    payload_obj=json.loads(payload)
    frag_num = payload_obj["InputInformation"]["KinesisVideo"]["FragmentNumber"]
    kvs_stream = kvs_video_client.get_media(
        StreamARN='arn:aws:kinesisvideo:us-west-2:632033863834:stream/LiveRekognitionVideoAnalysisBlog/1586205325374', # kinesis stream arn
        StartSelector={'StartSelectorType': 'FRAGMENT_NUMBER', 'AfterFragmentNumber': frag_num} 
    )
    print("The kvs_stream is here:",kvs_stream)
    
    with open('/tmp/streams.mkv', 'wb') as f:
        streamBody = kvs_stream['Payload'].read(1024*2048) # can tweak this
        f.write(streamBody)
        # use openCV to get a frame
        cap = cv2.VideoCapture('/tmp/streams.mkv')
        # total = count_frames(cap)
        # print("The total number of frames in the video : ",total)
        cap.set(1,220)
        # use some logic to ensure the frame being read has the person, something like bounding box or median'th frame of the video etc
        ret, frame = cap.read() 
        cv2.imwrite('/tmp/frame.jpg', frame)
        s3_client = boto3.client('s3')
        s3_client.upload_file(
            '/tmp/frame.jpg',
            'rekframebucket', # replace with your bucket name
            'frame.jpg',
            ExtraArgs={'ACL': 'public-read'}
        )
        cap.release()
        print('Image uploaded to bucket rekognition-photos')

    rekognition = boto3.client('rekognition')
    s3 = boto3.resource(service_name='s3')
    bucket = s3.Bucket('rekognition-photos')
    target_response = requests.get("https://rekframebucket.s3-us-west-2.amazonaws.com/frame.jpg")
    target_response_content = target_response.content

    recognized_image_key = ''
    faceId = ''
    collectionId = 'rekVideoBlog'
    confidence = 0
    rekognition_response = {}
    print("This is the length of object : ",bucket.objects.all())
    for obj in bucket.objects.all():
        # Compare frame captured from webcam to the image in S3 bucket.
        #print (obj.name)
        recognized_image_key = obj.key
        print ("This is object key : ",obj.key)
        url = "https://{0}.s3-us-west-2.amazonaws.com/{1}".format("rekognition-photos", obj.key)
        print (url)
        source_response = requests.get(url)
        source_response_content = source_response.content
        print("This is source content : ", source_response_content)
        print("This is target content : ", target_response_content)
        # print(source_response_content," is the source and : ",target_response_content," is the target\n")
        try:
            rekognition_response = rekognition.compare_faces(SourceImage={'Bytes': source_response_content}, TargetImage={'Bytes': target_response_content}) 
            rekognition_index_response = rekognition.index_faces(CollectionId=collectionId, Image={ 'S3Object': {'Bucket':'rekognition-photos','Name':recognized_image_key} })
        except:
            return {
                'statusCode':200,
                'body': json.dumps('Failed to recognize face in image frame')
            }
        for faceRecord in rekognition_index_response['FaceRecords']:
         faceId = faceRecord['Face']['FaceId']

        for faceMatch in rekognition_response['FaceMatches']:
            confidence = int(faceMatch['Face']['Confidence'])
        
        if confidence>70:
            break

        print ("This is the rekognition response : ",rekognition_response)
    
    # if 'FaceMatches' in rekognition_response.keys():
    for faceMatch in rekognition_response['FaceMatches']:
        confidence = int(faceMatch['Face']['Confidence'])

    #ses = boto3.client('ses')
    if confidence and confidence>70 :
        print(faceId," : is the faceid and it face MATCHES!!")
        # COMMENT THE BELOW LINE DURING ACTUAL DEPLOYMENT!!!
        # faceId = "3dd97dc8-db9e-48fe-a91e-e72dae97f591"
        ################################################
        # photos = []
        # photo_dict = {}
        # bucket = rekognition_bucket
        # createdTimeStamp = int(time.time())
        # objKey = name+str(createdTimeStamp)+".jpg"
        # photo_dict["objectKey"] = objKey
        # photo_dict["bucket"] = bucket
        # photo_dict["createdTimeStamp"] = createdTimeStamp
        
        # photos.append(photo_dict)
        # copy_to_photos_bucket(objKey)
        # print("Moved image to rekognition bucket")
        # update_visitors(photos, faceId)
        # print("Updated visitors photos")
        otp = generateOTP()
        print("Generated OTP!",otp)
        inserted = insert_into_passcodes(otp, faceId)
        print("inserted into passcodes")
        if(inserted):
            appended = append_to_visitors(faceId)
            print("The result of appending: ",appended)
            send_otp(otp, faceId)
            print("Sent otp to phone")
        else:
            print("The message has been recently sent\n")

    else:
        print(faceId, "is not matching with anything else")
        sns = boto3.client("sns")
        msg = "Is this someone you know? " + "https://rekframebucket.s3-us-west-2.amazonaws.com/frame.jpg" + "\n To allow access enter details in the link " + "http://virtual-door-files.s3-website-us-west-2.amazonaws.com/contact_form/"
        sub = "Unknown Visitor Alert"
        print("Message is : ",msg)
        inserted = insert_into_passcodes("-1","owner")
        if(inserted):
            response = sns.publish(
                PhoneNumber='+13478818075',
                Message=msg,
                Subject=sub
            )
        else:
            print("Owner has already recently received a message\n")
        
        print(response," Is the output of the message sending\n")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
