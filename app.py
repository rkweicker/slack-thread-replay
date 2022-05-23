import time
import datetime
import json

# Slack specific imports
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


# Load slack app tokens
# TODO: figure out as an environment variable
with open('tokens.json') as f:
   data = json.load(f)

SLACK_APP_TOKEN = data['SLACK_APP_TOKEN']
SLACK_BOT_TOKEN = data['SLACK_BOT_TOKEN']


# Install the Slack app and get xoxb- token in advance
app = App(token=SLACK_BOT_TOKEN)
client = WebClient(token=SLACK_BOT_TOKEN)

KEY_WORD = '!replay'
KEY_WORD_TEST = '!replay-test'
KEY_WORD_DELETE = '!replay-delete'

def print_date(date):
    date_time = datetime.datetime.fromtimestamp(float(date))
    return date_time.strftime('%H:%M:%S')

# Reformat the 'block' returned in the original message in the proper format
# for the new message.
def format_blocks(blocks):

    new_blocks = []
    for block in blocks:
        if block['type'] == 'image':
            new_block = dict()
            new_block['type'] = block['type']
            new_block['image_url'] = block['image_url']
            new_block['alt_text'] = block['alt_text']
            embedded = dict()
            embedded['type'] = block['title']['type']
            embedded['text'] = block['title']['text']
            embedded['emoji'] = block['title']['emoji']
            new_block['title'] = embedded
            new_blocks.append(new_block)

    if len(new_blocks) == 0:
        return None 
    else:
        return new_blocks

    
# Get the actual conversation channel ID for an IM. To be used for deleting conversatinos.
def find_im_conversation(user):
    #TODO - try/catch
    result = client.conversations_list(types='im')

    for channel in result['channels']:
        if channel['user'] == user:
            return channel['id']

    return None

# Get the username from the user_id
def get_username(user_id):
    #TODO - try/catch
    result = client.users_info(user=user_id)
    username = result['user']['name']
    return (username, result['user']['profile']['image_original'])

# Delete all the scheduled messages by user_id
def delete_scheduled_messages(user_id):

    channel_id = find_im_conversation(user_id)
    #TODO - try/catch
    result = client.chat_scheduledMessages_list(channel=channel_id)

    for message in result['scheduled_messages']:
        try:
            # Call the chat.deleteScheduledMessage method using the built-in WebClient
            #TODO - try/catch
            delete_result = client.chat_deleteScheduledMessage(
                channel=channel_id,
                scheduled_message_id=message['id']
            )

        except SlackApiError as e:
            #logger.error(f"Error deleting scheduled message: {e}")
            print(e)

    return True

# Skips certain meseages in the replay. 
# TODO - should I skip messages from @Thread Replay?
def skip_message_check(message):
    return

# Example as a slack command. Cannot be used in a thread.
@app.command("/hello-socket-mode")
def hello_command(ack, body):
    user_id = body["user_id"]
    ack(f"Hi, <@{user_id}>!")


# Given the details of the thread where the replay is requested, get all the replies
# and send as an IM to the requesting user
def send_ims(channel_id,thread_ts,end_ts, user, send_message=True):

    #TODO - try/catch
    # Gets all replies
    replies = client.conversations_replies(channel=channel_id, ts=thread_ts)

    # Delay 15 seconds because of weird issue where scheduling happens in the past
    # TODO - check this
    start_time = time.time() + 15
    print("Current time: " + str(print_date(time.time())))
    
    # First message of the thread should be a new post via chat_postMessage so it's thread_ts can be used
    # for subsequent replies
    first_message = True
    
    for message in replies['messages']:
        ts = message['ts']
        
        # Don't need to send the bot's reply message
        if ts == end_ts:
            break

        # Calculate the delta between the current message and the original message
        delta = float(ts) - float(thread_ts)
        bot_message = "<@" + message['user'] + ">:  " + message['text']    
        
        schedule_timestamp = start_time + delta

        #TODO probably don't need the send_message test mode anymore
        if send_message:
            print(bot_message)
            
            if first_message:
                #TODO - try/catch
                result = client.chat_postMessage(
                    channel=user,
                    text=bot_message,
                    blocks=format_blocks(message['blocks']) if 'blocks' in message.keys() else None,
                    post_at=int(schedule_timestamp),
                    link_names=True
                )
                # Get the resulting ts to use as the thread_ts for all scheduled messages
                first_ts = result['ts']
                first_message = False
            else :
                
                # Limit - > 30 / 5 minutes will fail per documentations
                #TODO - try/catch
                result = client.chat_scheduleMessage(
                    channel=user,
                    text=bot_message,
                    blocks=format_blocks(message['blocks']) if 'blocks' in message.keys() else None,
                    post_at=int(schedule_timestamp),
                    thread_ts=first_ts,
                    link_names=True)



def get_username_text(user):
    if user['profile']['display_name'] == '':
        return user['profile']['real_name'] 
    else:
        return user['profile']['display_name'] 

def log_message(event):
    #TODO - try/catch
    result = client.users_info(user=event['user'])
    user = get_username_text(result['user'])

    return user + " called me and said: " + event['text']

# Handles any IMs to the bot
@app.event("message")
def im_message(event,say):

    print(log_message(event))

    if event['text'].lower() == KEY_WORD_DELETE:
        say("Stopping all scheduled messages.")
        delete_scheduled_messages(event['user'])
    else:
        say('I can do two things: \n'+
            'To stop a current thread replay type `!replay-delete`. Note - slack has a bug where anything scheduled in the next 5 minutes can not be deleted\n' +
            'To start a new thread replay, go to that thread and mention me and say `!replay` like this: `@Thread Replay !replay`')


# Handles all @ mentions
@app.event("app_mention")
def event_test(event,say):
    print(log_message(event))

    # For now - if the message is NOT in a thread, do nothing.
    words = event['text'].split()
    if 'thread_ts' not in event.keys():
        say("I only work in a thread!")
        return
    
    keyword_spoken = False

    # Find the keyword and handle accordingly.
    for message in words:

        if message.lower() == KEY_WORD:       
            #TODO - try/catch
            result = client.chat_postMessage(
                channel=event['channel'],
                thread_ts = event['thread_ts'],
                text="DMing you this thread!",
                link_names=True
            )
            send_ims(event['channel'],event['thread_ts'],event['ts'],event['user'])
            keyword_spoken = True
            break

        elif message.lower() == KEY_WORD_TEST:
            #TODO - try/catch
            send_ims(event['channel'],event['thread_ts'],event['ts'],event['user'],False)
            result = client.chat_postMessage(
                channel=event['channel'],
                thread_ts = event['thread_ts'],
                text="DMing you this thread - test mode (no message)",
                link_names=True
            )
            keyword_spoken = True
            
            break

        elif message.lower() == KEY_WORD_DELETE:
            #TODO - try/catch
            delete_scheduled_messages(event['user'])
            result = client.chat_postMessage(
                channel=event['channel'],
                thread_ts = event['thread_ts'],
                text="Deleting all scheduled replay messages"
            )
            keyword_spoken = True
        else:
            continue

    
    # If the user is in a thread but doesn't say a keyword, then say this
    if keyword_spoken == False:
        #TODO - try/catch
        result = client.chat_postMessage(
            channel=event['channel'],
            thread_ts = event['thread_ts'],
            text="Please use either !replay or !replay-delete",
            link_names=True
        )

# Boilerplate
if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()