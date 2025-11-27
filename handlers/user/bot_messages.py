from aiogram import Router, F
from aiogram.types import Message


router = Router()


# @router.message(F.photo)
# async def receive_photo(message: Message):
#     photo = message.photo[-1]  # Беремо останнє (найбільше за розміром) фото
#     photo_id = photo.file_id

#     print(f"Отримано photo_id: {photo_id}")

#     await message.answer(
#         f"🖼 Фото отримано!\nID цього фото:\n<code>{photo_id}</code>",
#         parse_mode="HTML"
#     )



# @router.message(F.video)
# async def receive_video(message: Message):
#     video = message.video
#     video_id = video.file_id

#     print(f"Отримано video_id: {video_id}")

#     await message.answer(
#         f"🎬 Відео отримано!\nID цього відео:\n<code>{video_id}</code>",
#         parse_mode="HTML"
#     )