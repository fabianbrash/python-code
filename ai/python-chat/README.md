```README goes here```


#### You can build with


````
docker build -t local/qwen-chat-app:0.0.2 .

````


#### You can run with the below docker command


````
docker run -d \
  -p 5001:5001 \
  -e RAFAY_API_KEY="MY_JWT_TOKEN" \
  --name chat-bot-instance \
  local/qwen-chat-app:0.0.2

````
