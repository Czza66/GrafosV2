from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from solver import resolver_ruta_optima

app = FastAPI()

class CoordenadasInput(BaseModel):
    coordenadas: List[str]

@app.post("/resolver/")
async def resolver(coordenadas_input: CoordenadasInput):
    try:
        resultado = resolver_ruta_optima(coordenadas_input.coordenadas)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
