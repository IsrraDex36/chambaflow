import os
from google import genai
from google.genai import types

def answer_indeed_question(question_text, options, user_context, api_key):
    """
    Usa Gemini para responder una pregunta de Indeed basándose en el contexto del usuario.
    Si hay options (lista de strings), devuelve la mejor opción exacta.
    Si options está vacío, devuelve una respuesta de texto corta (máx. 1-2 oraciones o un número).
    """
    if not api_key or api_key == "TU_API_KEY_AQUI":
        print("[LLM] API key no configurada, devolviendo respuesta por defecto.")
        return options[0] if options else "Sí"
        
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        Eres un asistente automatizado de reclutamiento aplicand a una vacante para el siguiente candidato:
        Perfil del candidato: {user_context}
        
        Te harán una pregunta de un formulario de postulación de Indeed.
        """
        
        if options:
            prompt += f"""
            Pregunta de selección múltiple: "{question_text}"
            Opciones disponibles: {options}
            
            Tu tarea: Devuelve EXACTAMENTE y SOLAMENTE el texto de la opción que mejor se adapte al candidato. No añadas comillas, puntos, ni ninguna otra palabra.
            """
        else:
            prompt += f"""
            Pregunta abierta: "{question_text}"
            
            Tu tarea: Responde la pregunta de forma MUY concisa basándote en el perfil. Si piden años de experiencia, solo da el número (ej: "3"). Si es una pregunta de Sí/No, responde "Sí" o "No". No des explicaciones a menos que sea necesario. Máximo 10 palabras. Si la respuesta no está clara en el perfil, haz tu mejor estimación positiva.
            """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,  # Baja temperatura para consistencia
            ),
        )
        
        respuesta_limpia = response.text.strip()
        print(f"[LLM] Q: '{question_text}' -> A: '{respuesta_limpia}'")
        return respuesta_limpia
        
    except Exception as e:
        print(f"[LLM] Error llamando a Gemini: {e}")
        return options[0] if options else "2"
