import json
import codecs
import os
import re
import bs4
from logging import getLogger, StreamHandler, FileHandler, Formatter, DEBUG, INFO
import htmlGetter
from jsonpath_ng import parse
import argparse
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
from pprint import pformat
import csv

logger = getLogger(__name__)

# 生放送の動画のIDをVIDEO_IDに代入
OUTPUT_DIR = "./CommentFiles/"


class InitialData:
    def __init__(self, initial_data):
        self._initial_data = initial_data


class FirstInitialData(InitialData):

    _continuation_path = parse(
        "contents.twoColumnWatchNextResults.conversationBar.liveChatRenderer.continuations[0].reloadContinuationData.continuation"
    )

    def __init__(self, initial_data):
        super().__init__(initial_data)
        self.continuation = self._continuation_path.find(initial_data)[0].value


class NextInitialData(InitialData):

    _continuation_path = parse("continuationContents.liveChatContinuation.continuations[0].liveChatReplayContinuationData.continuation")

    def __init__(self, initial_data):
        super().__init__(initial_data)
        matches = self._continuation_path.find(initial_data)
        if matches:
            self.continuation = matches[0].value
        else:
            self.continuation = None

    @property
    def actions(self):
        return self._initial_data["continuationContents"]["liveChatContinuation"].get("actions", [])

    @property
    def lines(self):
        # 最後の一行は continuation が入っているのでスキップ
        for action in self.actions[:-1]:
            action_name = list(action.keys())[0]
            chat_item_actions = action[action_name]['actions']

            if len(chat_item_actions) > 1:
               logger.debug('chat_item_actions: %s' % pformat(chat_item_actions, indent=2, width=1, compact=False))

            chat_item_action = chat_item_actions[0]
            chat_item_action_name = list(chat_item_action.keys())[0]

            if chat_item_action_name != 'replayChatItemAction' and chat_item_action_name != 'addChatItemAction':
                logger.debug('unkown_action: %s' % pformat(chat_item_action, indent=2, width=1, compact=False))
                continue

            if chat_item_action_name == 'addChatItemAction' or chat_item_action_name == 'addLiveChatTickerItemAction':
                item = chat_item_action[chat_item_action_name]['item']

                renderer_name = list(item.keys())[0]

                if renderer_name == 'liveChatTextMessageRenderer':
                    pass
                else:
                    logger.debug('unkown_renderer: %s' % pformat(item, indent=2, width=1, compact=False))
                    continue

                # elif renderer_name == 'liveChatPaidMessageRenderer':
                #     pass
                # elif renderer_name == 'liveChatPaidStickerRenderer':
                #     pass
                # elif renderer_name == 'liveChatTickerPaidStickerItemRenderer':
                #     pass
                # elif renderer_name == 'liveChatTickerPaidMessageItemRenderer':
                #     pass
                # elif renderer_name == 'liveChatMembershipItemRenderer':
                #     pass
                # elif renderer_name == 'liveChatTickerSponsorItemRenderer':
                #     pass
                # elif renderer_name == 'liveChatPlaceholderItemRenderer':
                #     pass

                comment_data = item[renderer_name]

                time = comment_data['timestampText'].get('simpleText', None)
                name = comment_data['authorName'].get('simpleText', None)
                text = comment_data['message']['runs'][0].get('text', None)
                yield {
                    'time': time,
                    'name': name,
                    'text': text
                }
 
            else:
                pass



# htmlファイルから目的のjsonファイルを取得する
def get_initial_data(url, first=False):
    html = htmlGetter.get_html(url)
    soup = bs4.BeautifulSoup(html, "html.parser")
    script = next(filter(lambda s: 'window["ytInitialData"]' in str(s), soup.find_all("script")), None)

    if not script:
        raise Exception('<script> tag was not found')

    json_line = re.findall(r"window\[\"ytInitialData\"\] = (.*);", script.string)[0]
    json_dict = json.loads(json_line)

    # logger.debug("ytInitialData: %s" % json.dumps(json_dict, indent="  ", ensure_ascii=False))

    return NextInitialData(json_dict) if not first else FirstInitialData(json_dict)


def main(args):

    stream_handler = StreamHandler()
    stream_handler.setLevel(INFO)
    logger.addHandler(stream_handler)

    if args.debug:
        file_handler = FileHandler(filename="comment_saver_%s.log" % args.video_id, encoding='utf-8', mode='w')
        file_handler.setLevel(DEBUG)
        file_handler.setFormatter(Formatter("%(asctime)s %(levelname)8s %(message)s"))
        logger.addHandler(file_handler)
        logger.setLevel(DEBUG)
    else:
        logger.setLevel(INFO)

    url = urlunparse(('https', 'www.youtube.com', '/watch', None, urlencode({'v': args.video_id}), None))

    # 最初の continuation を得る
    initial_data = get_initial_data(url, first=True)
    continuation = initial_data.continuation
    logger.info("InitialContinuation: %s" % continuation)

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with codecs.open(OUTPUT_DIR + args.video_id + '.tsv', mode='w', encoding='utf-8') as f:
        tsv_writer = csv.DictWriter(f, fieldnames=['time', 'name', 'text'], dialect=csv.excel_tab)
        tsv_writer.writeheader()

        while continuation:
            url = urlunparse(('https', 'www.youtube.com', '/live_chat_replay', None, urlencode({'continuation': continuation}), None))
            initial_data = get_initial_data(url)
            for line in initial_data.lines:
                tsv_writer.writerow(line)
            continuation = initial_data.continuation
            logger.info("NextContinuation: %s" % continuation)


def VideoId(string):
    url = urlparse(string)
    if(url.scheme != "https" or
       url.hostname != "www.youtube.com" or
       url.path != "/watch"
       ):
        raise argparse.ArgumentTypeError('specified url is not that of YouTube')

    query = parse_qs(url.query)

    if 'v' not in query:
        raise argparse.ArgumentTypeError('Video id parameter is not found')

    return query.get('v')[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true",
                        help="increase output verbosity")
    parser.add_argument("video_id", metavar='<youtube url>', help="youtube movie url", type=VideoId)
    args = parser.parse_args()

    main(args)
