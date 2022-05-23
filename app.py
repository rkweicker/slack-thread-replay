import os
import time
import datetime
import logging
import json

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import json

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

    blocks = [{

	}, {
		'type': 'context',
		'block_id': 'Ao=SW',
		'elements': [{
			'type': 'image',
			'image_url': 'https://a.slack-edge.com/dc483/img/plugins/giphy/service_32.png',
			'alt_text': 'giphy logo'
		}, {
			'type': 'mrkdwn',
			'text': 'Posted using /giphy',
			'verbatim': False
		}]}]

    if len(new_blocks) == 0:
        return None 
    else:
        return new_blocks

    

def find_im_conversation(user):
    result = client.conversations_list(types='im')

    for channel in result['channels']:
        if channel['user'] == user:
            return channel['id']

    return None


def get_username(user_id):

    result = client.users_info(user=user_id)
    username = result['user']['name']
    return (username, result['user']['profile']['image_original'])

def delete_scheduled_messages(user):

    channel_id = find_im_conversation(user)
    result = client.chat_scheduledMessages_list(channel=channel_id)

    for message in result['scheduled_messages']:
        try:
            # Call the chat.deleteScheduledMessage method using the built-in WebClient
            delete_result = client.chat_deleteScheduledMessage(
                channel=channel_id,
                scheduled_message_id=message['id']
            )
            # Log the result
            #logger.info(result)

        except SlackApiError as e:
            #logger.error(f"Error deleting scheduled message: {e}")
            print(e)

    return True

def skip_message_check(message):
    return


@app.command("/hello-socket-mode")
def hello_command(ack, body):
    user_id = body["user_id"]
    ack(f"Hi, <@{user_id}>!")

def send_dms(channel_id,thread_ts,end_ts, user, send_message=True):
    replies = client.conversations_replies(channel=channel_id, ts=thread_ts)
    start_time = time.time() + 15
    print("Current time: " + str(print_date(time.time())))
    first_message = True
    for message in replies['messages']:
        ts = message['ts']
        if ts == end_ts:
            break

        delta = float(ts) - float(thread_ts)
        bot_message = "<@" + message['user'] + ">:  " + message['text']    
        
        schedule_timestamp = start_time + delta
        #print(print_date(schedule_timestamp))

        # Call the chat.scheduleMessage method using the WebClient
        if send_message:
            print(message['text'])
            if first_message:
                #username, image = get_username(message['user'])
                result = client.chat_postMessage(
                    channel=user,
                    text=bot_message,
                    blocks=format_blocks(message['blocks']) if 'blocks' in message.keys() else None,
                    post_at=int(schedule_timestamp),
                    link_names=True
                )
                first_ts = result['ts']
                first_message = False
            else :
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

    result = client.users_info(user=event['user'])
    user = get_username_text(result['user'])

    return user + " called me and said: " + event['text']



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


@app.event("app_mention")
def event_test(event,say):
    print(log_message(event))

    words = event['text'].split()
    if 'thread_ts' not in event.keys():
        say("I only work in a thread!")
        return
    
    keyword_spoken = False

    for message in words:
        if message.lower() == KEY_WORD:       
            result = client.chat_postMessage(
                channel=event['channel'],
                thread_ts = event['thread_ts'],
                text="DMing you this thread!",
                link_names=True
            )
            send_dms(event['channel'],event['thread_ts'],event['ts'],event['user'])
            keyword_spoken = True
            break

        elif message.lower() == KEY_WORD_TEST:
            send_dms(event['channel'],event['thread_ts'],event['ts'],event['user'],False)
            result = client.chat_postMessage(
                channel=event['channel'],
                thread_ts = event['thread_ts'],
                text="DMing you this thread - test mode (no message)",
                link_names=True
            )
            keyword_spoken = True
            
            break

        elif message.lower() == KEY_WORD_DELETE:
            delete_scheduled_messages(event['user'])
            result = client.chat_postMessage(
                channel=event['channel'],
                thread_ts = event['thread_ts'],
                text="Deleting all scheduled replay messages"
            )
            keyword_spoken = True
        else:
            continue

    
    if keyword_spoken == False:
        result = client.chat_postMessage(
            channel=event['channel'],
            thread_ts = event['thread_ts'],
            text="Please use either !replay or !replay-delete",
            link_names=True
        )


if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()