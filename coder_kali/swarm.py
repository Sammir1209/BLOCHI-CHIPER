"""
coder_kali/swarm.py - Swarm Engine: Orquestador Multi-Agente Táctico.

Implementa un sistema de enjambre donde múltiples agentes especializados
(RECON, EXPLOIT, AUDITOR) trabajan coordinados bajo un orquestador central.

Cada agente tiene:
- Rol y especialización definidos
- Conjunto de herramientas preferidas (del MCP Hub)
- Prompt de sistema personalizado para su dominio
- Cola de tareas asignadas por el orquestador

El orquestador:
- Analiza la misión del operador
- Divide en sub-tareas y asigna al agente más apropiado
- Consolida resultados en un reporte táctico unificado
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum


class AgentRole(Enum):
    """Roles especializados de los sub-agentes del enjambre."""
    RECON = "recon"
    EXPLOIT = "exploit"
    AUDITOR = "auditor"
    ORCHESTRATOR = "orchestrator"


@dataclass
class SwarmTask:
    """Tarea individual asignada a un sub-agente."""
    id: str
    description: str
    assigned_agent: AgentRole
    priority: int = 1  # 1 = más alta
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    commands: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)


@dataclass
class SwarmAgent:
    """Definición de un sub-agente especializado del enjambre."""
    role: AgentRole
    name: str
    description: str
    preferred_tools: List[str]
    expertise: List[str]
    prompt_context: str


# ─── Definición de Sub-Agentes Especializados ──────────────────────────────────

SWARM_AGENTS = {
    AgentRole.RECON: SwarmAgent(
        role=AgentRole.RECON,
        name="Agente RECON (Explorador / OSINT)",
        description="Especialista en reconocimiento, mapeo de superficie de ataque y recolección de inteligencia",
        preferred_tools=["nmap", "subfinder", "httpx", "whatweb", "theharvester", "ffuf", "gobuster"],
        expertise=[
            "Escaneo de puertos y servicios",
            "Descubrimiento de subdominios",
            "Fingerprinting de tecnologías web",
            "Enumeración de directorios y archivos ocultos",
            "OSINT y recolección de emails/metadata",
            "Análisis DNS y registros WHOIS",
            "Mapeo de infraestructura y red",
        ],
        prompt_context=(
            "[SUB-AGENTE RECON ACTIVADO]\n"
            "Tu rol es EXCLUSIVAMENTE de reconocimiento y mapeo. Ejecuta:\n"
            "1. Escaneo de puertos con nmap (top 1000, -sV, -T4)\n"
            "2. Descubrimiento de subdominios con subfinder\n"
            "3. Sondeo HTTP con httpx-toolkit (tech-detect, status-code)\n"
            "4. Fingerprinting de tecnologías con whatweb\n"
            "5. Fuzzing de rutas con ffuf o gobuster\n"
            "Reporta TODOS los hallazgos de forma estructurada al Orquestador."
        ),
    ),
    AgentRole.EXPLOIT: SwarmAgent(
        role=AgentRole.EXPLOIT,
        name="Agente EXPLOIT (Ingeniería de Ataque / Scripting)",
        description="Especialista en explotación, bypass de autenticación, inyección y scripting ofensivo",
        preferred_tools=["sqlmap", "hydra", "john", "nuclei", "wpscan"],
        expertise=[
            "Inyección SQL automatizada y manual",
            "Bypass de autenticación y CSRF",
            "Fuerza bruta de credenciales",
            "Cracking de hashes",
            "Explotación de vulnerabilidades conocidas (CVE)",
            "Scripting ofensivo en Python",
            "Manipulación de sesiones y tokens",
            "Escalada de privilegios",
        ],
        prompt_context=(
            "[SUB-AGENTE EXPLOIT ACTIVADO]\n"
            "Tu rol es EXCLUSIVAMENTE de explotación y ataque. Ejecuta:\n"
            "1. Pruebas de inyección SQL con sqlmap (--batch --threads=10)\n"
            "2. Fuerza bruta con hydra si hay formularios de login\n"
            "3. Scripts Python personalizados para bypass de auth/CSRF\n"
            "4. Explotación de CVEs detectados por el Agente RECON\n"
            "5. Dumping completo de bases de datos comprometidas\n"
            "Documenta cada vector explotado con evidencia técnica."
        ),
    ),
    AgentRole.AUDITOR: SwarmAgent(
        role=AgentRole.AUDITOR,
        name="Agente AUDITOR (Analista Forense y OPSEC)",
        description="Especialista en análisis de vulnerabilidades, verificación OPSEC y generación de reportes",
        preferred_tools=["nuclei", "wpscan", "nikto"],
        expertise=[
            "Escaneo de vulnerabilidades con templates",
            "Auditoría de CMS (WordPress, Joomla, Drupal)",
            "Verificación de anonimato (VPN/Tor/Proxy)",
            "Análisis de logs y trazas forenses",
            "Validación de hallazgos y falsos positivos",
            "Generación de reportes de impacto",
            "Verificación de códigos HTTP y WAF",
            "Control de OPSEC y limpieza de huellas",
        ],
        prompt_context=(
            "[SUB-AGENTE AUDITOR ACTIVADO]\n"
            "Tu rol es EXCLUSIVAMENTE de auditoría y verificación. Ejecuta:\n"
            "1. Escaneo de vulnerabilidades con nuclei (-severity high,critical)\n"
            "2. Auditoría CMS con wpscan si aplica\n"
            "3. Verificación de OPSEC (IP pública, estado VPN/Tor)\n"
            "4. Validación de hallazgos del Agente RECON y EXPLOIT\n"
            "5. Consolidación de evidencias en reporte estructurado\n"
            "Asegura que todos los datos estén guardados de forma organizada."
        ),
    ),
}


# ─── Patrones de Detección de Misiones para Asignación Automática ──────────────

MISSION_PATTERNS = {
    AgentRole.RECON: [
        r"\b(?:escan[ea]|scan|reconocimiento|recon|mapear?|descubr[ie]|enumera|subdominios?|puertos?|servicios?)\b",
        r"\b(?:fingerprint|whatweb|httpx|nmap|subfinder|osint|whois|dns|dig)\b",
        r"\b(?:fuzz(?:ing|ear)?|directorios?|rutas?|endpoints?|gobuster|ffuf|feroxbuster)\b",
        r"\b(?:theharvester|amass|assetfinder|shodan|censys)\b",
    ],
    AgentRole.EXPLOIT: [
        r"\b(?:exploit[ae]|atacar?|inyecci[oó]n|sqli?|sql\s*injection|xss|rce|lfi|rfi)\b",
        r"\b(?:bypass|brute\s*force|fuerza\s*bruta|credenciales?|password|contrase[ñn]a)\b",
        r"\b(?:sqlmap|hydra|john|metasploit|msfconsole|payload|shell|reverse)\b",
        r"\b(?:dump(?:ear|ing)?|extraer?|exfiltrar?|volcar?|crackear?|descifrar?)\b",
        r"\b(?:login|autenticaci[oó]n|csrf|token|sesi[oó]n|cookie)\b",
    ],
    AgentRole.AUDITOR: [
        r"\b(?:auditar?|auditor[ií]a|vulnerabilidad(?:es)?|vuln|cve|nuclei|nikto)\b",
        r"\b(?:report[ea]|informe|hallazgo|impacto|recomendaci[oó]n|remediaci[oó]n)\b",
        r"\b(?:wpscan|wordpress|cms|joomla|drupal)\b",
        r"\b(?:opsec|anonimato|vpn|tor|proxy|huella|rastro|limpieza)\b",
        r"\b(?:verificar?|validar?|confirmar?|comprobar?)\b",
    ],
}


class SwarmOrchestrator:
    """
    Orquestador central del enjambre multi-agente.
    
    Funcionalidades:
    - Analiza la misión del operador y detecta qué agentes son necesarios
    - Divide misiones complejas en sub-tareas especializadas
    - Genera el contexto del enjambre para inyectar en el system prompt
    - Coordina la secuencia de ejecución (RECON → EXPLOIT → AUDITOR)
    - Consolida hallazgos en reportes unificados
    """

    def __init__(self):
        self.agents = SWARM_AGENTS
        self.active_tasks: List[SwarmTask] = []
        self.mission_log: List[str] = []
        self._task_counter = 0
        self.swarm_active = False

    def analyze_mission(self, user_message: str) -> List[AgentRole]:
        """
        Analiza el mensaje del operador y determina qué sub-agentes
        son necesarios para completar la misión.
        
        Returns:
            Lista ordenada de roles de agentes que deben participar.
        """
        lower_msg = user_message.lower()
        detected_roles = set()

        for role, patterns in MISSION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower_msg, re.IGNORECASE):
                    detected_roles.add(role)
                    break

        # Si no se detecta ningún rol específico, usar RECON + EXPLOIT por defecto
        if not detected_roles:
            return [AgentRole.RECON, AgentRole.EXPLOIT]

        # Ordenar por secuencia lógica: RECON → EXPLOIT → AUDITOR
        priority_order = [AgentRole.RECON, AgentRole.EXPLOIT, AgentRole.AUDITOR]
        ordered = [r for r in priority_order if r in detected_roles]

        return ordered

    def is_complex_mission(self, user_message: str) -> bool:
        """
        Determina si una misión es lo suficientemente compleja para
        activar el modo enjambre multi-agente.
        
        Criterios:
        - Involucra 2+ roles de agentes
        - Contiene palabras clave de misión completa (auditoría completa, pentest full)
        - El mensaje es extenso (>100 chars) con múltiples objetivos
        """
        roles = self.analyze_mission(user_message)
        
        # Palabras clave que activan el enjambre automáticamente
        swarm_triggers = [
            r"\b(?:auditor[ií]a\s+completa|pentest\s+(?:full|completo)|escaneo\s+total)\b",
            r"\b(?:análisis\s+completo|reconocimiento\s+y\s+explotación)\b",
            r"\b(?:evalua(?:ción|r)\s+(?:de\s+seguridad|completa))\b",
            r"\b(?:misión|operación|engagement)\s+(?:completa|total|integral)\b",
        ]
        
        has_trigger = any(re.search(pat, user_message, re.IGNORECASE) for pat in swarm_triggers)
        
        return len(roles) >= 2 or has_trigger

    def create_mission_plan(self, user_message: str, target: str = "") -> List[SwarmTask]:
        """
        Crea un plan de misión con tareas asignadas a cada sub-agente.
        
        Args:
            user_message: Mensaje original del operador
            target: Objetivo/dominio/IP si se puede extraer
        
        Returns:
            Lista de SwarmTasks ordenadas por prioridad y secuencia.
        """
        roles = self.analyze_mission(user_message)
        tasks = []
        
        target_str = target or self._extract_target(user_message)

        for i, role in enumerate(roles):
            agent = self.agents[role]
            self._task_counter += 1

            if role == AgentRole.RECON:
                task = SwarmTask(
                    id=f"SWARM-{self._task_counter:03d}",
                    description=f"Reconocimiento y mapeo de superficie de ataque en {target_str or 'objetivo'}",
                    assigned_agent=role,
                    priority=1,
                    commands=self._generate_recon_commands(target_str),
                )
            elif role == AgentRole.EXPLOIT:
                task = SwarmTask(
                    id=f"SWARM-{self._task_counter:03d}",
                    description=f"Explotación de vectores detectados en {target_str or 'objetivo'}",
                    assigned_agent=role,
                    priority=2,
                    commands=self._generate_exploit_commands(target_str),
                )
            elif role == AgentRole.AUDITOR:
                task = SwarmTask(
                    id=f"SWARM-{self._task_counter:03d}",
                    description=f"Auditoría de vulnerabilidades y generación de reporte en {target_str or 'objetivo'}",
                    assigned_agent=role,
                    priority=3,
                    commands=self._generate_audit_commands(target_str),
                )
            else:
                continue

            tasks.append(task)

        self.active_tasks = tasks
        self.swarm_active = True
        return tasks

    def _extract_target(self, text: str) -> str:
        """Intenta extraer el dominio, IP o URL objetivo del mensaje del operador."""
        # Buscar URLs
        url_match = re.search(r'https?://[\w\.\-/]+', text)
        if url_match:
            return url_match.group(0)
        
        # Buscar dominios
        domain_match = re.search(r'\b(?:[\w\-]+\.)+(?:com|org|net|edu|gov|io|co|pe|es|mx|ar|cl)\b', text, re.IGNORECASE)
        if domain_match:
            return domain_match.group(0)
        
        # Buscar IPs
        ip_match = re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', text)
        if ip_match:
            return ip_match.group(0)
        
        # Buscar rangos CIDR
        cidr_match = re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}\b', text)
        if cidr_match:
            return cidr_match.group(0)

        return ""

    def _generate_recon_commands(self, target: str) -> List[str]:
        """Genera comandos de reconocimiento sugeridos para el target."""
        if not target:
            return []
        cmds = []
        # Determinar si es IP o dominio
        is_ip = bool(re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', target))
        
        if is_ip:
            cmds.append(f"nmap -sS -sV -T4 --top-ports 1000 --host-timeout 3m {target}")
        else:
            clean_domain = re.sub(r'https?://', '', target).split('/')[0]
            cmds.append(f"subfinder -d {clean_domain} -silent -o subdomains.txt")
            cmds.append(f"cat subdomains.txt | httpx-toolkit -status-code -title -tech-detect -follow-redirects -json -o httpx_results.json")
            cmds.append(f"nmap -sS -sV -T4 --top-ports 1000 --host-timeout 3m {clean_domain}")
            cmds.append(f"whatweb {target} -a 3 -v")
        
        return cmds

    def _generate_exploit_commands(self, target: str) -> List[str]:
        """Genera comandos de explotación sugeridos para el target."""
        if not target:
            return []
        return [
            f"nuclei -u {target} -severity high,critical -rl 150 -timeout 5 -j -o nuclei_findings.json",
        ]

    def _generate_audit_commands(self, target: str) -> List[str]:
        """Genera comandos de auditoría sugeridos para el target."""
        if not target:
            return []
        cmds = [
            f"nuclei -u {target} -severity medium,high,critical -rl 150 -timeout 5 -j -o audit_findings.json",
        ]
        # Si parece WordPress
        if "wp" in target.lower() or "wordpress" in target.lower():
            cmds.append(f"wpscan --url {target} --enumerate u,vp --random-user-agent")
        return cmds

    def generate_swarm_context(self, user_message: str) -> str:
        """
        Genera el contexto del enjambre para inyectar en la respuesta del agente.
        Solo se activa si la misión es lo suficientemente compleja.
        """
        if not self.is_complex_mission(user_message):
            return ""

        roles = self.analyze_mission(user_message)
        target = self._extract_target(user_message)
        
        lines = [
            "\n[🐝 MODO ENJAMBRE MULTI-AGENTE ACTIVADO]",
            f"Objetivo detectado: {target or '(pendiente de identificar)'}",
            f"Sub-agentes asignados: {len(roles)}",
            "",
        ]

        for i, role in enumerate(roles, 1):
            agent = self.agents[role]
            tools_str = ", ".join(agent.preferred_tools[:5])
            lines.append(f"  Fase {i}: {agent.name}")
            lines.append(f"    Herramientas: {tools_str}")
            lines.append(f"    {agent.prompt_context.split(chr(10))[1] if chr(10) in agent.prompt_context else ''}")
            lines.append("")

        # Agregar comandos sugeridos
        tasks = self.create_mission_plan(user_message, target)
        if tasks:
            lines.append("Secuencia de comandos sugerida:")
            for task in tasks:
                lines.append(f"  [{task.id}] {task.description}")
                for cmd in task.commands[:3]:
                    lines.append(f"    $ {cmd}")
                lines.append("")

        lines.append(
            "INSTRUCCIÓN: Ejecuta las fases en orden. Emite los comandos de cada fase "
            "dentro de bloques <ejecutar_comando> y analiza los resultados antes de avanzar "
            "a la siguiente fase."
        )

        return "\n".join(lines)

    def get_agent_context_for_prompt(self, role: AgentRole) -> str:
        """Retorna el contexto especializado de un sub-agente para inyectar en el prompt."""
        agent = self.agents.get(role)
        if not agent:
            return ""
        
        tools_str = ", ".join(agent.preferred_tools)
        expertise_str = "\n".join(f"  - {e}" for e in agent.expertise)
        
        return (
            f"\n{agent.prompt_context}\n"
            f"Herramientas preferidas: {tools_str}\n"
            f"Áreas de expertise:\n{expertise_str}\n"
        )

    def update_task_status(self, task_id: str, status: str, result: str = "", findings: Optional[List[str]] = None):
        """Actualiza el estado de una tarea del enjambre."""
        for task in self.active_tasks:
            if task.id == task_id:
                task.status = status
                if result:
                    task.result = result
                if findings:
                    task.findings = findings
                break

    def get_mission_summary(self) -> str:
        """Genera un resumen del estado actual de la misión del enjambre."""
        if not self.active_tasks:
            return "[Enjambre inactivo — No hay tareas asignadas]"

        lines = ["[📊 ESTADO DE MISIÓN DEL ENJAMBRE]"]
        
        for task in self.active_tasks:
            agent = self.agents[task.assigned_agent]
            status_icon = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
            }.get(task.status, "❓")
            
            lines.append(f"  {status_icon} [{task.id}] {agent.name}")
            lines.append(f"    Descripción: {task.description}")
            lines.append(f"    Estado: {task.status.upper()}")
            
            if task.findings:
                lines.append(f"    Hallazgos: {len(task.findings)}")
                for finding in task.findings[:3]:
                    lines.append(f"      • {finding}")
            lines.append("")

        completed = sum(1 for t in self.active_tasks if t.status == "completed")
        total = len(self.active_tasks)
        lines.append(f"Progreso total: {completed}/{total} fases completadas")

        return "\n".join(lines)

    def deactivate(self):
        """Desactiva el modo enjambre."""
        self.swarm_active = False
        self.active_tasks = []

    def get_status(self) -> Dict[str, Any]:
        """Retorna el estado actual del orquestador."""
        return {
            "swarm_active": self.swarm_active,
            "active_tasks": len(self.active_tasks),
            "completed_tasks": sum(1 for t in self.active_tasks if t.status == "completed"),
            "agents_available": list(self.agents.keys()),
        }
