/* Ejemplo de llamadas a sistema (ficheros: crea un fichero)

	Compilar con:		gcc file1.c -o file1
	Ejecutar con:		./file1
*/

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>

#define BLKSIZE	100 		//tamaño del buffer
                                 
int main (void)
{
  int fd, bytes_escritos;	//descriptor de fichero
  char buffer[BLKSIZE];	
  mode_t modo = S_IRWXU; 	// modo de r,w,x para el propietario

  strcpy(buffer, "Esto es un ejemplo\n");
  // abre el fichero ejemplo en modo lectura/escritura o lo crea si no existe
  if ((fd = open ("ejemplo", O_RDWR | O_CREAT, modo))== -1)
	perror ("Error al abrir o crear el fichero");
	//muestra un mensaje de error si no puede abrir/crear el fichero
  else
	bytes_escritos = write(fd, buffer, strlen(buffer));
	// escribe buffer de tamaño sizeof(buffer) en fd 
  exit(0);
}
