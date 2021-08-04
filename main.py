import os
import telebot  #upm package(pyTelegramBotAPI)
import subprocess

from peewee import IntegerField, IntegrityError, Model, SqliteDatabase

from test import main

TokenBot = os.getenv("TOKEN")
dz = telebot.TeleBot(TokenBot)

AdmChat = os.getenv('ADM_CHAT') #Canal privado del grupo

db = SqliteDatabase('sqlite3') #Database para permisos del /feedback

##################### CLASES PARA BASE DE DATOS #####################

class Block(Model):
  user_id = IntegerField(unique=True)
  class Meta:
    database = db

class Message(Model):
  from_ = IntegerField()
  id = IntegerField(unique=True)
  class Meta:
    database = db

db.create_tables([Block, Message]) #Se crean las tablas de la base de datos

##################### CLASES PARA FILTROS DE USUARIOS #####################

class Filters:
  def is_user(msg):
    return (msg.chat.id != AdmChat and msg.chat.type == "private")

  def is_admin(msg):
    return msg.chat.id == AdmChat

  def is_answer(msg):
    return (
      msg.chat.id == int(AdmChat)
      and msg.reply_to_message is not None
      and msg.reply_to_message.forward_date is not None
    )

  def is_blocked(msg):
    return Block.select().where(Block.user_id == msg.chat.id).exists()

  def is_not_blocked(msg):
    return not Block.select().where(Block.user_id == msg.chat.id).exists()


##################### INICIO DEL BOT #####################
# Comando para empezar a usar el bot por primera vez

@dz.message_handler(commands=['start'])
def opening(msg):
  userID = msg.from_user.id
  userNAME = msg.from_user.first_name
  userTag = "["+userNAME+"](tg://user?id="+str(userID)+")"
  dz.reply_to(msg, "Bienvenido "+userTag, parse_mode="Markdown")
  dz.send_message(msg.chat.id, "Yo soy Diozelyne, tu asistente emocional de confianza! ")
  dz.send_message(msg.chat.id, "Prueba usando el comando /emotion 👇")

##################### COMANDO HELP #####################
# Ayuda acerca de los comandos o como hacer uso del bot

@dz.message_handler(commands=['help'])
def help_msg(msg):
  dz.send_message(msg.chat.id, """\
  Ayúda de usuario:

    /start             |  Inicializar el bot
    /help             |  Mostrar la ayuda al usuario
    /emotion      |  Analizar el estado de animo
    /feedback     |  Reporte de bugs y sugerencias

  *_Diozelyne Team_*
  """, parse_mode="Markdown")

##################### SPEECH EMOTION RECOGNITION #####################
# Reconocer el estado de animo del usuario segun su nota de voz 

@dz.message_handler(commands=['emotion'])
def need_audio(msg): 
  msg = dz.send_message(msg.chat.id, "Por favor, envíame una nota de voz")
  dz.register_next_step_handler(msg, audio_worker) 

def audio_worker(msg): 
  if msg.content_type == 'voice':
    dz.reply_to(msg, 'Procesando tu audio...')
        
    fileID = msg.voice.file_id
    file = dz.get_file(fileID)
    down_file = dz.download_file(file.file_path)
    with open('test.ogg', 'wb') as f:
      f.write(down_file)

    src_filename = 'test.ogg'
    dest_filename = 'test.wav'

    process = subprocess.run(
      ['ffmpeg', '-i', src_filename, dest_filename, '-y'])
    if process.returncode != 0:
      raise Exception("Error")
    result = main()

    dz.send_message(msg.chat.id, "Usted actualmente está " +result)
  else:
    dz.reply_to(msg, "Oooopps, parece que esto no es una nota de voz!")
    dz.send_message(msg.chat.id, "Puedes intentarlo de nuevo usando /emotion")

##################### COMANDO DE FEEDBACK #####################
# Enviar sugerencias al equipo de desarrollo

@dz.message_handler(commands=['feedback'], func=lambda msg: Filters.is_user(msg) and Filters.is_not_blocked(msg))
def get_question(msg):
  sent = dz.send_message(msg.chat.id, 'Detalle a continuación su sugreencia por favor: ')
  dz.register_next_step_handler(sent, suggest)

def suggest(msg):
  if msg.content_type == 'text':
    sent = dz.forward_message(AdmChat, msg.chat.id, msg.message_id)
    dz.send_message(msg.chat.id, 'Su sugerencia fue enviada exitosamente!')
    Message.create(from_=msg.chat.id, id=sent.message_id).save()
  else:
    dz.reply_to(msg, 'Por favor, solamente enviar texto describiendo su sugerencia')

@dz.message_handler(commands=['feedback'], func=Filters.is_blocked)
def get_error_question(msg):
    dz.send_message(msg.chat.id, 'Error: Usted no puede enviar sugerencias')

##################### COMANDO PARA REVOCAR USO DE /feedback #####################
# Comando usado para bloquearle el uso del /feedback al usuario remitente

@dz.message_handler(commands=["block"], func=Filters.is_answer)
def block_user(msg):
    user_id = (Message.select().where(Message.id == msg.reply_to_message.message_id).get().from_)
    try:
        Block.create(user_id=user_id).save()
    except IntegrityError:
        pass

    dz.send_message(msg.chat.id,'El usuario {user_id} tiene denegado el uso del comando /feedback'.format(user_id=user_id))

##################### COMANDO PARA REVOCAR BLOQUEO DE /feedback #####################
# Comando para quitarle el bloqueo del comando /feedback al usuario bloqueado

@dz.message_handler(commands=["unblock"], func=Filters.is_answer)
def unblock(msg):
    user_id = (Message.select().where(Message.id == msg.reply_to_message.message_id).get().from_
    )
    try:
        Block.select().where(Block.user_id == user_id).get().delete_instance()
    except Block.DoesNotExist:
        pass

    dz.send_message( msg.chat.id, 'El usuario {user_id} tiene permitdo el uso del comando /feedback'.format(user_id=user_id)
    )

##################### RESPONDER A SUGERENCIAS #####################

@dz.message_handler(content_types=['text'], func=Filters.is_answer)
def answer_question(msg):
  to_user_id = (Message.select().where(Message.id == msg.reply_to_message.message_id).get().from_)
  dz.send_message(to_user_id, msg.text)
  dz.send_message(msg.chat.id, 'Eh enviado tu respuesta!', reply_to_message_id=msg.message_id)

##################### GUARDADO DE PASOS E INICIADOR DEL BOT #####################

dz.enable_save_next_step_handlers(delay=2)
dz.load_next_step_handlers()

dz.polling()