const PUBLIC_IP = "54.255.177.143"; // Replace with your server's current public IP

const CONFIG = {
  RASA_SERVER_URL: `http://${PUBLIC_IP}:5005`, // Use the public IP dynamically
  SOCKET_PATH: "/socket.io/",
  TITLE: "Chat with us!",
  INIT_PAYLOAD: "/introduce",
  SHOW_MESSAGE_DATE: true,
  STORAGE: "session",
};