from __future__ import annotations

import streamlit as st

def render_manual_content() -> None:
    st.markdown(
        """
        Esta app ayuda a procesar **una carrera por vez** a partir del PDF del
        plan de estudio y de la matriz Excel de tributacion. Al finalizar,
        puedes revisar un resumen, comprobar la deteccion de carrera/facultad,
        descargar un respaldo local y, si corresponde, publicar en la base
        online.
        """
    )

    st.markdown(
        """
        ### Archivos que debes subir
        - **PDF del plan de estudio** de la carrera que quieres procesar.
        - **Matriz Excel de tributacion** correspondiente a esa carrera.
        """
    )

    st.markdown(
        """
        ### Paso a paso
        1. Ve a la pestaña **Procesar carrera**.
        2. Sube el PDF del plan de estudio.
        3. Sube la matriz Excel de tributacion.
        4. Presiona **Procesar carrera**.
        5. Revisa el resumen generado, la carrera detectada, la facultad
           detectada y la previsualizacion del consolidado.
        6. Si necesitas un respaldo, usa **Descargar consolidado Excel**.
        7. Si todo esta correcto, completa la revision humana y elige la accion
           online que corresponde.
        """
    )

    st.markdown(
        """
        ### Que revisar antes de publicar
        - Que la **carrera** detectada sea la correcta.
        - Que la **facultad** detectada sea la correcta.
        - Que el resumen no muestre observaciones que deban corregirse antes de
          continuar.
        - Que la previsualizacion coincida con la carrera que quieres cargar.
        """
    )

    st.info(
        "Descargar el Excel solo genera un respaldo local en tu sesion. "
        "Publicar online si modifica la base compartida."
    )

    st.markdown(
        """
        ### Cuando elegir cada accion online
        - **Publicar nueva carrera**: cuando la carrera aun no existe en la base
          online.
        - **Reemplazar carrera**: cuando la carrera ya existe y necesitas
          sustituir sus filas por una nueva version.
        - **Cancelar**: cuando prefieres no publicar todavia o quieres revisar
          nuevamente antes de tomar una decision.
        """
    )

    st.warning(
        "Si la carrera o la facultad detectada no son correctas, no publiques. "
        "Corrige los insumos y vuelve a procesar la carrera."
    )
    st.warning(
        "Si aparecen advertencias, leelas antes de continuar. Algunas pueden "
        "requerir una revision manual del PDF o de la matriz."
    )

    st.success(
        "Despues de una publicacion exitosa, considera descargar el Excel como "
        "respaldo y continuar con la siguiente carrera solo cuando confirmes que "
        "ya no necesitas volver a publicar la actual."
    )
