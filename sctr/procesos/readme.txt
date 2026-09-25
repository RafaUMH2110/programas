Programas ejemplo manejo de procesos POSIX
------------------------------------------------------
file1.c		Ejemplo llamadas al sistema creacion de ficheros
file2.c		Ejemplo llamadas al sistema lectura de ficheros

p1.c		Creacion basica de procesos con fork()
p2.c		Creacion de procesos y espera la terminacion del hijo con wait()
p3.c		Ejemplo de uso de la funcion  execl()
p4.c		Ejemplo de uso de la funcion  execvp()
p5.c		Ejemplo de acceso al mismo fichero desde varios procesos
p6.c		Ejemplo de acceso a memoria dinamica en varios procesos
matar.c		Ejemplo de uso de la funcion kill()

planificador.c	Ejemplo de uso de cambio de politica de planificacion de procesos
planificador1.c	Ejemplo de uso de cambio de politica de planificacion de procesos (sin sleep)
planificador2.c	Ejemplo de uso de lectura quantum RR

sem1.c		Ejemplo de uso de semaforos nombrados para el problema Productor/Consumidor

sem2.c		Ejemplo de uso de semaforos nombrados (secci—n critica)
sem2r.c			" - Seccion de entrada/salida desactivadas


sem3.c		Ejemplo de uso de semaforos nombrados para sincronizar la ejecucion de dos procesos 
sem3r.c			" - Seccion de entrada/salida desactivadas

ipc1.c		Ejemplo de uso de memoria compartida entre procesos con semaforos nombrados
ipc2.c		Ejemplo de uso de semaforos no nombrados + memoria compartida (secci—n critica)