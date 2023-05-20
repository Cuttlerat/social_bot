import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

API_TOKEN = os.environ.get("TG_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

GOOD_STICKER_ID = "AgADAgADf3BGHA"
BAD_STICKER_ID = "AgADAwADf3BGHA"

db_conn_url = URL(
    drivername="postgresql+psycopg2",
    username=os.environ.get("DATABASE_USER"),
    password=os.environ.get("DATABASE_PASSWORD"),
    host=os.environ.get("DATABASE_HOST"),
    port=os.environ.get("DATABASE_PORT"),
    database=os.environ.get("DATABASE_NAME"),
    query={},
)

Base = declarative_base()


class SocialBot(Base):
    __tablename__ = "social_bot"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    username = Column(String(255))
    social_rating = Column(Integer)
    chat_id = Column(BigInteger)
    last_update = Column(DateTime, default=func.now())


# Create the database engine and session

engine = create_engine(db_conn_url)
Session = sessionmaker(bind=engine)
session = Session()


@dp.message_handler(commands=["social_rank"])
async def social_rank(message: types.Message):
    records = (
        session.query(SocialBot)
        .filter_by(chat_id=message.chat.id)
        .order_by(SocialBot.social_rating.desc())
        .all()
    )
    entries = (f"{record.username}: {record.social_rating}" for record in records)
    await message.reply("\n".join(entries))


@dp.message_handler(content_types=types.ContentTypes.STICKER)
async def process_sticker(message: types.Message):
    if not message.reply_to_message:
        return

    user = message.from_user
    username = user.username or user.full_name
    reply_user = message.reply_to_message.from_user
    reply_username = reply_user.username or reply_user.full_name
    sticker_id = message.sticker.file_unique_id

    if reply_user.is_bot:
        await message.reply("Can't edit bot social credit")
        return
    if user.id == reply_user.id:
        await message.reply("Can't edit your own social credit")
        return

    record = (
        session.query(SocialBot)
        .filter_by(user_id=reply_user.id, chat_id=message.chat.id)
        .first()
    )
    if not record:
        record = SocialBot(
            user_id=reply_user.id,
            username=reply_username,
            chat_id=message.chat.id,
            social_rating=0,
        )
        session.add(record)
    elif record.last_update + timedelta(minutes=1) > datetime.now():
        await message.reply(
            "You have to wait one minute before changing social rating again!"
        )
        return

    msg_verb = ""

    if sticker_id == GOOD_STICKER_ID:
        record.social_rating += 20
        msg_verb = "increased"
    if sticker_id == BAD_STICKER_ID:
        record.social_rating -= 20
        msg_verb = "decreased"

    record.username = reply_username
    record.last_update = datetime.now()

    msg = f"{username} {msg_verb} rank of {reply_username}!\nNow their social credit is {record.social_rating} points"
    session.commit()
    await message.reply(msg)


if __name__ == "__main__":
    try:
        executor.start_polling(dp, skip_updates=False)
    except Exception as e:
        logger.exception("An error occurred while starting the bot")
