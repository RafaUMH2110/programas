#
#       @(#)Makefile
#
#
#
# If you want to compile for debugging, change "-O" to "-g"
#
LIBS_SOLARIS	= -lposix4 
LIBS_LINUX = -lrt 
LIBS_MAC = 

LIBS = $(LIBS_LINUX) 

CFLAGS		=  -g 
CC		= gcc
INCLUDE		= 


# if you want special to pass special loader options to ld, set
# LDFLAGS= ...
#
	   
OBJS		= p1 \
		  p2 \
		  p3 \
		  p4 \
		  p5 \
		  p6 \
		  matar \
		  planificador \
		  planificador1 \
		  planificador2 \
		  sem1 \
		  sem2 \
		  sem2r \
		  sem3 \
		  sem3r \
		  ipc1 \
		  ipc2 \
		  ej2 \
		  ej3 \
		  file1 \
		  file2 \

all: $(OBJS) 


p1: p1.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
p2: p2.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
p3: p3.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
p4: p4.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
p5: p5.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
p6: p6.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
matar: matar.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
planificador: planificador.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)

planificador1: planificador1.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)

planificador2: planificador2.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)

sem1: sem1.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
sem2: sem2.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
sem2r: sem2r.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
sem3: sem3.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
sem3r: sem3r.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
ipc1: ipc1.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
ipc2: ipc2.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
ej2: ej2.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)
	
ej3: ej3.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)

file1: file1.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)

file2: file2.c 
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $@.c $(LIBS)


clean:
	rm -f core *%
