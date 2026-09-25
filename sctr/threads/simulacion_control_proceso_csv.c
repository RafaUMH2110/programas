/**
 * simulacion_control_proceso_csv.c
 * 
 * Simulación de tanque con control PID y exportación de datos a CSV.
 * Ideal para análisis posterior en Python/Matlab.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <math.h>
#include <time.h>

// --- Estructura de Estado ---
typedef struct {
    double altura_actual;
    double setpoint;
    double flujo_entrada;
    double flujo_salida;
    double error;
    double error_integral;
    double error_anterior;
    
    // PID
    double Kp, Ki, Kd;
    
    // Físicos
    double area_tanque;
    double coef_salida;
    double max_altura;
    
    // Control
    int ejecutando;
    double periodo_muestreo;
    double tiempo_simulacion;
    double tiempo_transcurrido;
    
    // Archivo de datos
    FILE* archivo_csv;
} EstadoSistema;

EstadoSistema estado;
pthread_mutex_t lock_estado = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t cond_muestreo = PTHREAD_COND_INITIALIZER;

// --- Utilidades ---
void obtener_tiempo_absoluto(struct timespec *ts, double segundos) {
    struct timespec ahora;
    clock_gettime(CLOCK_REALTIME, &ahora);
    ts->tv_sec = ahora.tv_sec + (time_t)segundos;
    ts->tv_nsec = ahora.tv_nsec;
}

// --- Lógica de Negocio ---
double calcular_flujo_salida(double altura) {
    if (altura < 0) altura = 0;
    return estado.coef_salida * sqrt(altura);
}

double calcular_control_pid() {
    double error = estado.setpoint - estado.altura_actual;
    estado.error = error;
    
    // Anti-windup simple
    if (estado.flujo_entrada > 0.0 && estado.flujo_entrada < 1.0) {
        estado.error_integral += error * estado.periodo_muestreo;
    }
    
    double derivada = (error - estado.error_anterior) / estado.periodo_muestreo;
    double salida = (estado.Kp * error) + 
                    (estado.Ki * estado.error_integral) + 
                    (estado.Kd * derivada);
    
    if (salida > 1.0) salida = 1.0;
    if (salida < 0.0) salida = 0.0;
    
    estado.flujo_entrada = salida;
    estado.error_anterior = error;
    return salida;
}

void actualizar_proceso_fisico() {
    estado.flujo_salida = calcular_flujo_salida(estado.altura_actual);
    
    double flujo_real_entrada = estado.flujo_entrada * 0.1; 
    double flujo_real_salida = estado.flujo_salida * 0.05; 
    
    double derivada_h = (flujo_real_entrada - flujo_real_salida) / estado.area_tanque;
    estado.altura_actual += derivada_h * estado.periodo_muestreo;
    
    if (estado.altura_actual < 0) estado.altura_actual = 0;
    if (estado.altura_actual > estado.max_altura) estado.altura_actual = estado.max_altura;
}

// --- Hilos ---
void* hilo_proceso(void* arg) {
    (void)arg;
    while (estado.ejecutando) {
        struct timespec ts;
        obtener_tiempo_absoluto(&ts, estado.periodo_muestreo);
        pthread_mutex_lock(&lock_estado);
        pthread_cond_timedwait(&cond_muestreo, &lock_estado, &ts);
        actualizar_proceso_fisico();
        pthread_mutex_unlock(&lock_estado);
    }
    return NULL;
}

void* hilo_controlador(void* arg) {
    (void)arg;
    while (estado.ejecutando) {
        struct timespec ts;
        obtener_tiempo_absoluto(&ts, estado.periodo_muestreo);
        pthread_mutex_lock(&lock_estado);
        pthread_cond_timedwait(&cond_muestreo, &lock_estado, &ts);
        
        calcular_control_pid();
        
        // Consola
        printf("\r[Sim] t=%.2fs | h=%.3fm | SP=%.3fm | q_in=%.2f | e=%.3f", 
               estado.tiempo_transcurrido, 
               estado.altura_actual, 
               estado.setpoint, 
               estado.flujo_entrada, 
               estado.error);
        fflush(stdout);
        
        // CSV: Escribir datos
        // Formato: tiempo, altura, setpoint, flujo_entrada, flujo_salida, error
        fprintf(estado.archivo_csv, "%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n",
                estado.tiempo_transcurrido,
                estado.altura_actual,
                estado.setpoint,
                estado.flujo_entrada,
                estado.flujo_salida,
                estado.error);
        fflush(estado.archivo_csv); // Asegurar escritura en disco
        
        pthread_mutex_unlock(&lock_estado);
    }
    return NULL;
}

// --- Principal ---
int main() {
    printf("=== Simulación Tanque + CSV ===\n");
    
    // Entrada
    printf("Tiempo simulación (s): ");
    scanf("%lf", &estado.tiempo_simulacion);
    printf("Periodo muestreo (s): ");
    scanf("%lf", &estado.periodo_muestreo);
    printf("Setpoint (m): ");
    scanf("%lf", &estado.setpoint);
    
    // Físicos
    estado.area_tanque = 1.0;
    estado.coef_salida = 0.5;
    estado.max_altura = 2.0;
    estado.altura_actual = 0.0;
    
    // PID
    printf("Kp: "); scanf("%lf", &estado.Kp);
    printf("Ki: "); scanf("%lf", &estado.Ki);
    printf("Kd: "); scanf("%lf", &estado.Kd);
    
    // Inicializar
    estado.error = 0; estado.error_integral = 0; estado.error_anterior = 0;
    estado.ejecutando = 1;
    estado.tiempo_transcurrido = 0.0;
    
    // Abrir CSV
    estado.archivo_csv = fopen("datos_simulacion.csv", "w");
    if (!estado.archivo_csv) {
        perror("Error abriendo archivo CSV");
        return 1;
    }
    // Cabecera
    fprintf(estado.archivo_csv, "tiempo,altura,setpoint,flujo_entrada,flujo_salida,error\n");
    
    printf("\nIniciando simulación...\n");
    
    pthread_t thread_proceso, thread_control;
    pthread_create(&thread_proceso, NULL, hilo_proceso, NULL);
    pthread_create(&thread_control, NULL, hilo_controlador, NULL);
    
    struct timespec start_time, current_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);
    
    while (estado.ejecutando) {
        clock_gettime(CLOCK_MONOTONIC, &current_time);
        double elapsed = (current_time.tv_sec - start_time.tv_sec) + 
                         (current_time.tv_nsec - start_time.tv_nsec) / 1e9;
        
        estado.tiempo_transcurrido = elapsed;
        
        if (elapsed >= estado.tiempo_simulacion) {
            estado.ejecutando = 0;
            break;
        }
        
        pthread_mutex_lock(&lock_estado);
        pthread_cond_broadcast(&cond_muestreo);
        pthread_mutex_unlock(&lock_estado);
        
        usleep((unsigned long)(estado.periodo_muestreo * 1000000));
    }
    
    printf("\nSimulación finalizada. Datos guardados en 'datos_simulacion.csv'.\n");
    
    // Limpieza
    estado.ejecutando = 0;
    pthread_join(thread_proceso, NULL);
    pthread_join(thread_control, NULL);
    fclose(estado.archivo_csv);
    
    return 0;
}