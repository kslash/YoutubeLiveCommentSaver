import json
import codecs
import os
import sys
import re
import bs4
from logging import getLogger, StreamHandler, FileHandler, Formatter, DEBUG, WARN
import htmlGetter
from jsonpath_ng import jsonpath, parse

logger = getLogger(__name__)
stream_handler = StreamHandler()
stream_handler.setLevel(WARN)
logger.addHandler(stream_handler)

file_handler = FileHandler(filename="comment_saver.log", encoding='utf-8')
file_handler.setLevel(DEBUG)
file_handler.setFormatter(Formatter("%(asctime)s %(levelname)8s %(message)s"))
logger.addHandler(file_handler)
logger.setLevel(DEBUG)


# 生放送の動画のIDをVIDEO_IDに代入
VIDEO_ID = ""
OUTPUT_DIR = "./CommentFiles/"

CONTINUATION_URL_FORMAT = "https://www.youtube.com/live_chat_replay?continuation={continuation}"


# htmlファイルから目的のjsonファイルを取得する
def get_json(html):
    soup = bs4.BeautifulSoup(html, "html.parser")
    script = next(filter(lambda s: 'window["ytInitialData"]' in str(s), soup.find_all("script")), None)

    if not script:
        raise Exception('<script> tag was not found')

    json_line = re.findall(r"window\[\"ytInitialData\"\] = (.*);", script.string)[0]
    json_dict = json.loads(json_line)

    logger.debug(json.dumps(json_dict, indent="  ", ensure_ascii=False))

    return json_dict


initial_continuation_path = parse(
    "contents.twoColumnWatchNextResults.conversationBar.liveChatRenderer.continuations[0].reloadContinuationData.continuation"
)


# 最初の動画のURLからcontinuationを引っ張ってくる
def get_initial_continuation(url):
    html = htmlGetter.get_html(url)
    json_dict = get_json(html)
    continuation = initial_continuation_path.find(json_dict)[0].value
    logger.debug("InitialContinuation:" + continuation)
    return continuation


continuation_path = parse("continuationContents.liveChatContinuation.continuations[0].liveChatReplayContinuationData.continuation")


# htmlから抽出したjson形式の辞書からcontinuationの値を抜き出す
def get_continuation(json_dict):
    matches = continuation_path.find(json_dict)
    if matches:
        continuation = matches[0].value
        logger.debug("NextContinuation: " + continuation)
        return continuation
    else:
        logger.warning("Continuation NotFound")
        return None


# コメントデータから文字列を取得する
def get_chat_text(actions):
    lines = []
    for item in actions:
        logger.info("item:" + json.dumps(item, indent="  ", ensure_ascii=False))

        # ユーザー名やテキスト、アイコンなどのデータが入っている
        comment_data = item['replayChatItemAction']['actions'][0].get('addChatItemAction', None)
        if not comment_data:
            continue
        comment_data = comment_data['item'].get('liveChatTextMessageRenderer', None)

        if not comment_data:
            continue

        time = comment_data['timestampText'].get('simpleText', None)
        name = comment_data['authorName'].get('simpleText', None)
        text = comment_data['message']['runs'][0].get('text', None)
        line = "{time}\t{name}\t{text}\n".format(time=time, name=name, text=text)
        logger.debug(line)
        lines.append(line)

    # 最後の行のコメントデータが次のcontinuationの最初のコメントデータを一致するため切り捨て
    if len(lines) > 1:
        del lines[len(lines) - 1]
    return lines


# 与えられたcontinuationから順次コメントを取得する
def get_live_chat_replay(continuation):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with codecs.open(OUTPUT_DIR + VIDEO_ID + '.tsv', mode='a', encoding='utf-8') as f:
        while continuation:
            url = CONTINUATION_URL_FORMAT.format(continuation=continuation)
            html = htmlGetter.get_html(url)

            json_dict = get_json(html)

            # key:actions中に各ユーザーのコメントが格納されている
            actions = json_dict["continuationContents"]["liveChatContinuation"].get("actions", [])
            # 複数件のコメントをlist形式で取得
            lines = get_chat_text(actions)
            # 次のcontinuationを取得する
            continuation = get_continuation(json_dict)

            f.writelines(lines)
            f.flush()


if __name__ == "__main__":
    args = sys.argv
    if len(args) > 1:
        VIDEO_ID = args[1]

    url = "https://www.youtube.com/watch?v="+VIDEO_ID

    # 生放送の録画ページから最初のcontinuationを取得する
    initial_continuation = get_initial_continuation(url)
    get_live_chat_replay(initial_continuation)
