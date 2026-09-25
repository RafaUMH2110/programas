#
#       @(#)Makefile
#
#
#
# If you want to compile for debugging, change "-O" to "-g"
#
LIBS_SOLARIS	= -lposix4 -lpthread
LIBS_LINUX = -lrt -lpthread
LIBS_MAC = -lpthread

LIBS = $(LIBS_LINUX) 

CFLAGS		=  -g 
CC		= gcc
INCLUDE		= 


# if you want special to pass special loader options to ld, set
# LDFLAGS= ...
#
	   
OBJS		= th1 \
		  th2 \
		  th3 \
		  th4 \
		  th5 \
		  mutexth \
		  mutexth2 \
		  deposito1 \
		  deposito2 \
		  deposito3 \
		  deposito4 \

all: $(OBJS) 


th1: th1.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
th3: th3.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
th4: th4.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
mutexth: mutexth.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
mutexth2: mutexth2.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
deposito1: deposito1.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
deposito2: deposito2.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
deposito3: deposito3.c tiempo.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c tiempo.c $(LIBS)
	
deposito4: deposito4.c tiempo.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c tiempo.c $(LIBS)
	
	
clean:
	rm -f core *%
