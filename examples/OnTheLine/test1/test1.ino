#include <SPI.h>
#include <Ethernet.h>
byte mac[] = { 0x00, 0x03, 0x7B, 0x20, 0xFE, 0xED }; //00:03:7B:20:09:F5 is my hmi mac
byte ip[]  = { 192, 168, 1, 2 };
long randNumber;
EthernetServer server(2537);

#define D_SIZE 600
uint16_t D[D_SIZE];


// Setup test data
void writeFloatToD(int addr, float value) {
  union {
    float f;
    uint32_t i;
  } u;

  u.f = value;
  D[addr]     = (u.i >> 16) & 0xFFFF;
  D[addr + 1] = u.i & 0xFFFF;
}

void populate(){
  D[158] = random(50, 101);   // 50-100
  writeFloatToD(512, random(5000, 10001) / 100.0);
}


// BCC
byte xorBcc(byte *data, int len){
  byte bcc = 0;
  for (int i = 0; i < len; i++) bcc ^= data[i];
  return bcc;
}

void sendHex(EthernetClient &c, byte v){
  const char *h = "0123456789ABCDEF";
  c.write(h[(v >> 4) & 0xF]);
  c.write(h[v & 0xF]);
}


// Reply builder
void replyReadD(EthernetClient &c, int addr, int nbytes){
  byte buf[64];
  int p = 0;

  buf[p++] = 0x06;   // ACK
  buf[p++] = 'F';    // device
  buf[p++] = 'F';
  buf[p++] = '0';

  int words = nbytes / 2;

  for (int i = 0; i < words; i++){
    uint16_t v = D[addr + i];

    const char *h = "0123456789ABCDEF";
    buf[p++] = h[(v >> 12) & 0xF];
    buf[p++] = h[(v >> 8)  & 0xF];
    buf[p++] = h[(v >> 4)  & 0xF];
    buf[p++] = h[v & 0xF];
  }

  byte bcc = xorBcc(buf, p);

  c.write(buf, p);
  sendHex(c, bcc);
  c.write('\r');

  Serial.println("TX sent");
}

// Main handler
void handle(EthernetClient c){
  byte buf[64];
  int len = 0;

  while (c.connected()) {
    while (c.available()) {
      byte b = c.read();

      if (len < 64) buf[len++] = b;

      if (b == 0x0D){  // end of frame

        Serial.print("RX: ");
        for (int i = 0; i < len; i++){
          if (buf[i] < 16) Serial.print("0");
          Serial.print(buf[i], HEX);
          Serial.print(" ");
        }
        Serial.println();

        // VERY simple parse (hardcoded for now)
        if (buf[4] == 'R' && buf[5] == 'D'){

          char a[5] = {buf[6], buf[7], buf[8], buf[9], 0};
          char l[3] = {buf[10], buf[11], 0};

          int addr = atoi(a);
          int nbytes = strtol(l, NULL, 16);
          populate();
          replyReadD(c, addr, nbytes);
        }

        len = 0;
      }
    }
  }

  c.stop();
}

// Arduino setup
void setup(){
  Serial.begin(9600);
  Ethernet.begin(mac, ip);
  server.begin();
  populate();
  Serial.print("Listening on ");
  Serial.print(Ethernet.localIP());
  Serial.println(":2537");
  randomSeed(analogRead(0));
}


// Loop
void loop(){
  EthernetClient client = server.available();
  if (client) {
    Serial.println("Client connected");
    handle(client);
    Serial.println("Client done");
  }
}
/*
Client connected
RX: 05 46 46 30 52 44 30 35 31 32 30 34 32 31 0D 
TX sent
Client done

*/
