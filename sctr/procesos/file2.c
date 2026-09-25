/* Ejemplo de llamadas a sistema (ficheros: lee un fichero)

	Compilar con:		gcc file2.c -o file2
	Ejecutar con:		./file2
*/

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>

#define BLKSIZE	100 		//tamaño del buffer

int main(void)
{
  int fd, bytes_read;
  char buffer[BLKSIZE];
  
  if ((fd = open("ejemplo", O_RDWR))==-1)
	perror("Error al abrir el fichero");
  else
  {
	bytes_read = read(fd, buffer, BLKSIZE);
	buffer[bytes_read]='\0';
	printf("%s son %d  bytes\n", buffer, bytes_read);
  }
  exit(0);
}
