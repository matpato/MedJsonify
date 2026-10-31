#!/bin/bash
set -e

# =============================================================================
# MedJsonify -- standalone runner (no Airflow scheduler needed)
# =============================================================================
#
# Runs the same task functions as the Airflow DAG, each in its own Docker
# container, with the same volume mounts, PYTHONPATH and user as
# docker-compose.yml. The image is light: Python and requirements.txt only,
# no Airflow (the DAG file is imported with a stand-in, see run_task.py). jsonify.ini, bioner.ini,
# neo4j.ini and the Python code are used unchanged, so Airflow keeps working
# exactly as before: this is a second way to run the same pipeline.
#
# USAGE (from the MedJsonify main folder)
#   bash standalone/run_medjsonify.sh --list                 -- tasks found in the DAG
#   bash standalone/run_medjsonify.sh --check                -- packages the code needs but the image lacks
#   bash standalone/run_medjsonify.sh --shell 'COMMAND'      -- run a shell command in the container
#                                                               (same mounts; working folder /opt/airflow/dags)
#   bash standalone/run_medjsonify.sh --step ontologies --force-ontologies
#                                                            -- download and process all ontologies again
#   bash standalone/run_medjsonify.sh --lexicon doid.owl     -- process an ontology file that is already in
#                                                               NER/ontologies/data (process_ontology.sh)
#   bash standalone/run_medjsonify.sh                        -- all steps, in order
#   bash standalone/run_medjsonify.sh --step convert         -- one step only
#   bash standalone/run_medjsonify.sh --step 5               -- same, by number
#   bash standalone/run_medjsonify.sh --from ner             -- ner, validate, graph
#   bash standalone/run_medjsonify.sh --step stats           -- conversion stats only
#   bash standalone/run_medjsonify.sh --ds 2025-05-01        -- run date passed to the tasks
#   bash standalone/run_medjsonify.sh --rebuild --step 2     -- rebuild the image first
#   bash standalone/run_medjsonify.sh --dry-run              -- print the commands only
#
# STEPS (in order)
#   1   download     download the source files (DailyMed, Purple Book, Orange Book)
#   2   convert      XML/CSV/TXT -> JSON (jsonifyer)
#   2b  stats        conversion statistics for the paper (conversion_stats.py)
#   3   ontologies   download (URLs in NER/bioner.ini) and process DOID, ORDO, HPO,
#                    ChEBI; already-processed ones are skipped
#   3b  vocabulary   download the DrugBank vocabulary
#   4   preprocess   text preprocessing of the JSON files
#   5   ner          NER and entity linking (+ ner_metrics report)
#   6   validate     check the NER output
#   7   graph        load the results into Neo4j (starts Neo4j if needed)
#   8   export       export the graph from Neo4j to CSV (indicated.csv,
#                    contraindicated.csv, ... in database/output, for Pharmalink-KG)
#
# Neo4j (step 7): if the docker-compose Neo4j container (medjsonify_neo4j) is
# running or stopped, it is used (started if needed) on its own network.
# Otherwise a Neo4j container is started like the one in docker-compose.yml,
# reachable under the same host name "neo4j", so neo4j.ini works unchanged.
#
# Monitoring a run:
#   tail -f standalone/logs/$(ls -t standalone/logs/ | head -1)
# =============================================================================


# -----------------------------------------------------------------------
# 0. Paths and settings (override any of them with environment variables)
# -----------------------------------------------------------------------
STANDALONE=$(cd "$(dirname "$0")" && pwd -P)
MEDJSONIFY=${MEDJSONIFY:-$(dirname "$STANDALONE")}
cd "$MEDJSONIFY"

# Task function names in the DAG (run with --list to check them)
TASK_DOWNLOAD=${TASK_DOWNLOAD:-}                       # set to your download task's name
TASK_CONVERT=${TASK_CONVERT:-convert_files_to_json_task}
TASK_ONTOLOGIES=${TASK_ONTOLOGIES:-setup_ontologies_task}
# Ontology step: "fetch" = standalone/fetch_ontologies.py (URLs from bioner.ini),
#                "task"  = the DAG's own setup task (TASK_ONTOLOGIES)
ONTOLOGY_SOURCE=${ONTOLOGY_SOURCE:-fetch}
TASK_VOCABULARY=${TASK_VOCABULARY:-download_vocabulary_task}
TASK_PREPROCESS=${TASK_PREPROCESS:-preprocess_json_task}
TASK_NER=${TASK_NER:-ner_process_task}
TASK_VALIDATE=${TASK_VALIDATE:-validate_results_task}
TASK_GRAPH=${TASK_GRAPH:-send_to_neo4j_task}
TASK_EXPORT=${TASK_EXPORT:-export_graph_task}

# Docker image: light, without Airflow (standalone/Dockerfile), built with the
# main folder as build context (so COPY requirements.txt refers to this folder).
# To use the Airflow image instead: DOCKERFILE=$MEDJSONIFY/Dockerfile
IMAGE=${IMAGE:-medjsonify-standalone:latest}
DOCKERFILE=${DOCKERFILE:-$STANDALONE/Dockerfile}
BUILD_CONTEXT=${BUILD_CONTEXT:-$MEDJSONIFY}
# Docker command: plain "docker" if it works (e.g. Docker Desktop on a Mac),
# otherwise "sudo docker" (e.g. a Linux server). Override with DOCKER=...
if [ -z "$DOCKER" ]; then
    if docker info &>/dev/null; then DOCKER=docker; else DOCKER="sudo docker"; fi
fi
# Same as "user: 1000:0" in docker-compose.yml, with your own user id
DOCKER_USER=${DOCKER_USER-"$(id -u):0"}

# jsonifyer is installed inside the image (see standalone/Dockerfile).
# Only for developing jsonifyer itself: JSONIFYER_SRC=/path/to/jsonifyer/src
# mounts a local copy, which then takes precedence over the installed one.
JSONIFYER_SRC=${JSONIFYER_SRC:-}

# Neo4j, as in docker-compose.yml
NEO4J_CONTAINER=${NEO4J_CONTAINER:-medjsonify_neo4j}
NEO4J_IMAGE=${NEO4J_IMAGE:-neo4j:5}
NEO4J_AUTH=${NEO4J_AUTH:-neo4j/testpassword}
NEO4J_NETWORK=${NEO4J_NETWORK:-medjsonify-standalone}
NEO4J_VOLUME=${NEO4J_VOLUME:-medjsonify_standalone_neo4j_data}

ALL_STEPS=(download convert stats ontologies vocabulary preprocess ner validate graph export)


# -----------------------------------------------------------------------
# Defaults and arguments
# -----------------------------------------------------------------------
STEP="all"
FROM_STEP=""
DS=$(date +%Y-%m-%d)
NETWORK=""
DRY_RUN=0
LIST=0
CHECK=0
FORCE_ONTOLOGIES=0
SHELL_CMD=""
LEXICONS=()
REBUILD=0
TASK_PARAMS=()

step_name() {   # accept numbers as in Pharmalink-KG
    case "$1" in
        1) echo download ;;    2) echo convert ;;     2b) echo stats ;;
        3) echo ontologies ;;  3b) echo vocabulary ;; 4) echo preprocess ;;
        5) echo ner ;;         6) echo validate ;;    7) echo graph ;;
        8) echo export ;;
        *) echo "$1" ;;
    esac
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --step)     STEP=$(step_name "$2"); shift 2 ;;
        --from)     FROM_STEP=$(step_name "$2"); shift 2 ;;
        --ds)       DS="$2"; shift 2 ;;
        --network)  NETWORK="$2"; shift 2 ;;
        --param)    TASK_PARAMS+=(--param "$2"); shift 2 ;;
        --rebuild)  REBUILD=1; shift ;;
        --dry-run)  DRY_RUN=1; shift ;;
        --list)     LIST=1; shift ;;
        --check)    CHECK=1; shift ;;
        --force-ontologies) FORCE_ONTOLOGIES=1; shift ;;
        --shell)    SHELL_CMD="$2"; shift 2 ;;
        --lexicon)  LEXICONS+=("$2"); shift 2 ;;
        -h|--help)  sed -n '4,42p' "$0"; exit 0 ;;
        *)          echo "Unknown argument: $1"; exit 1 ;;
    esac
done

valid_step() { local s; for s in all "${ALL_STEPS[@]}"; do [ "$s" == "$1" ] && return 0; done; return 1; }
if ! valid_step "$STEP"; then echo "Unknown step: $STEP (use one of: ${ALL_STEPS[*]})"; exit 1; fi
if [ -n "$FROM_STEP" ] && ! valid_step "$FROM_STEP"; then echo "Unknown step: $FROM_STEP"; exit 1; fi

STEPS_TO_RUN=()
if [ -n "$FROM_STEP" ]; then
    started=0
    for s in "${ALL_STEPS[@]}"; do
        [ "$s" == "$FROM_STEP" ] && started=1
        [ $started == 1 ] && STEPS_TO_RUN+=("$s")
    done
elif [ "$STEP" == "all" ]; then
    STEPS_TO_RUN=("${ALL_STEPS[@]}")
else
    STEPS_TO_RUN=("$STEP")
fi


# -----------------------------------------------------------------------
# Logging (screen and file)
# -----------------------------------------------------------------------
LOG_FILE=""
if [ $DRY_RUN == 0 ] && [ $LIST == 0 ] && [ $CHECK == 0 ] && [ -z "$SHELL_CMD" ]; then
    LOG_DIR=$STANDALONE/logs
    mkdir -p "$LOG_DIR"
    LOG_FILE=$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log
    echo "Logging to $LOG_FILE"
    exec > >(tee -a "$LOG_FILE") 2>&1
fi

run() {   # print, then run unless --dry-run
    echo "+ $*"
    if [ $DRY_RUN == 0 ]; then "$@"; fi
}


# -----------------------------------------------------------------------
# Folders that docker-compose creates at start-up (created here on the host)
# -----------------------------------------------------------------------
if [ $DRY_RUN == 0 ]; then
    mkdir -p upload/downloads logs NER/ontologies/data NER/ontologies/scripts
    for t in xml_files csv_files txt_files; do
        mkdir -p jsonify/input/$t jsonify/output/$t \
                 NER/data/entities/$t NER/data/preprocessing/$t
    done
    chmod +x NER/ontologies/scripts/*.sh 2>/dev/null || true
fi


# -----------------------------------------------------------------------
# Volume mounts: the MedJsonify ones from docker-compose.yml
# -----------------------------------------------------------------------
# host path (relative to the main folder)  ->  container path
REQUIRED_MOUNTS=(
    "airflow/dags:/opt/airflow/dags/airflow_dags"
    "NER:/opt/airflow/dags/NER"
    "jsonify:/opt/airflow/dags/jsonify"
)
OPTIONAL_MOUNTS=(
    "airflow/dags/utils:/opt/airflow/dags/utils"
    "upload:/opt/airflow/dags/upload"
    "database:/opt/airflow/dags/database"
    "logs:/opt/airflow/logs"
)
# (the .ini files, jsonify/data and NER/ontologies/* that docker-compose also
#  lists are inside the folders above, so they are mounted with them)

DOCKER_ARGS=(--rm -w /opt/airflow)
for m in "${REQUIRED_MOUNTS[@]}"; do
    host=${m%%:*}; target=${m#*:}
    if [ ! -e "$MEDJSONIFY/$host" ]; then
        echo "ERROR: $MEDJSONIFY/$host not found -- is MEDJSONIFY the main folder?"
        exit 1
    fi
    DOCKER_ARGS+=(-v "$MEDJSONIFY/$host:$target")
done
for m in "${OPTIONAL_MOUNTS[@]}"; do
    host=${m%%:*}; target=${m#*:}
    [ -e "$MEDJSONIFY/$host" ] && DOCKER_ARGS+=(-v "$MEDJSONIFY/$host:$target")
done

if [ -n "$JSONIFYER_SRC" ]; then
    if [ ! -d "$JSONIFYER_SRC" ]; then echo "ERROR: JSONIFYER_SRC not found: $JSONIFYER_SRC"; exit 1; fi
    DOCKER_ARGS+=(-v "$(cd "$JSONIFYER_SRC" && pwd -P):/opt/airflow/dags/jsonifyer_src")
    JSONIFYER_NOTE="local source $(cd "$JSONIFYER_SRC" && pwd -P) (overrides the image)"
else
    JSONIFYER_NOTE="installed in the image (GitHub commit + pairs fix)"
fi

DOCKER_ARGS+=(-v "$STANDALONE:/opt/standalone:ro"
    -e PYTHONPATH=/opt/airflow/dags/jsonifyer_src:/opt/airflow/dags:/opt/airflow/dags/jsonify/src
    -e AIRFLOW_DAGS_DIR=/opt/airflow/dags/airflow_dags
    # only used if the image has Airflow (DOCKERFILE=main Dockerfile):
    # no Airflow database is needed, so point it at a throw-away SQLite file
    -e AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags/airflow_dags
    -e AIRFLOW__CORE__LOAD_EXAMPLES=False
    -e AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=sqlite:////tmp/airflow_standalone.db
    -e AIRFLOW__CORE__SQL_ALCHEMY_CONN=sqlite:////tmp/airflow_standalone.db
    -e PYTHONUNBUFFERED=1)
[ -n "$DOCKER_USER" ] && DOCKER_ARGS+=(--user "$DOCKER_USER")


echo "========================================"
echo "MedJsonify standalone pipeline"
echo "Date:       $(date)"
echo "Steps:      ${STEPS_TO_RUN[*]}"
echo "ds:         $DS"
echo "Folder:     $MEDJSONIFY"
echo "Docker:     $DOCKER"
echo "Image:      $IMAGE ($(basename "$(dirname "$DOCKERFILE")")/$(basename "$DOCKERFILE"))"
echo "jsonifyer:  $JSONIFYER_NOTE"
echo "========================================"


# -----------------------------------------------------------------------
# Build image if needed
# -----------------------------------------------------------------------
if [ $REBUILD == 1 ]; then
    run $DOCKER rmi "$IMAGE" 2>/dev/null || true
fi
if [ $DRY_RUN == 1 ] || [ $REBUILD == 1 ] || ! $DOCKER image inspect "$IMAGE" &>/dev/null; then
    [ -f "$DOCKERFILE" ] || { echo "ERROR: Dockerfile not found: $DOCKERFILE"; exit 1; }
    echo "Building $IMAGE"
    echo "  Dockerfile:    $DOCKERFILE"
    echo "  Build context: $BUILD_CONTEXT"
    run $DOCKER build -t "$IMAGE" -f "$DOCKERFILE" "$BUILD_CONTEXT"
else
    echo "Image $IMAGE already exists -- skipping build (use --rebuild to force)"
fi


container() {   # container <command...>
    local net=()
    [ -n "$NETWORK" ] && net=(--network "$NETWORK")
    run $DOCKER run "${DOCKER_ARGS[@]}" "${net[@]}" --entrypoint python3 "$IMAGE" "$@"
}

run_task() {    # run_task <task_function_name>
    container /opt/standalone/run_task.py "$1" --ds "$DS" "${TASK_PARAMS[@]}"
}

if [ $LIST == 1 ]; then
    container /opt/standalone/run_task.py --list
    exit 0
fi
container_shell() {   # container_shell <command string>
    local net=()
    [ -n "$NETWORK" ] && net=(--network "$NETWORK")
    run $DOCKER run "${DOCKER_ARGS[@]}" "${net[@]}" -w /opt/airflow/dags --entrypoint bash "$IMAGE" -c "$1"
}

if [ -n "$SHELL_CMD" ]; then
    container_shell "$SHELL_CMD"
    exit $?
fi

if [ ${#LEXICONS[@]} -gt 0 ]; then
    # Process ontology files already placed in NER/ontologies/data, with the
    # project's own process_ontology.sh (lexicon name = file name without .owl)
    for f in "${LEXICONS[@]}"; do
        f=$(basename "$f")
        if [ $DRY_RUN == 0 ] && [ ! -f "NER/ontologies/data/$f" ]; then
            echo "ERROR: NER/ontologies/data/$f not found"; exit 1
        fi
        step_header_line="Processing ontology file $f"
        echo ""; echo "----------------------------------------"; echo "$step_header_line"; echo "----------------------------------------"
        container_shell "cd /opt/airflow/dags/NER/ontologies/data && bash ../scripts/process_ontology.sh '$f' ."
    done
    echo ""; echo "Lexicons now in NER/ontologies/data:"
    ls NER/ontologies/data/*_links.tsv 2>/dev/null || true
    exit 0
fi

if [ $CHECK == 1 ]; then
    container /opt/standalone/check_imports.py /opt/airflow/dags
    exit $?
fi


# -----------------------------------------------------------------------
# Neo4j for the graph step
# -----------------------------------------------------------------------
ensure_neo4j() {
    if [ -n "$NETWORK" ]; then
        echo "Using Docker network $NETWORK"
        return
    fi
    if [ $DRY_RUN == 1 ]; then
        echo "(dry run) would use or start $NEO4J_CONTAINER on network $NEO4J_NETWORK"
        NETWORK=$NEO4J_NETWORK
        return
    fi

    if $DOCKER container inspect "$NEO4J_CONTAINER" &>/dev/null; then
        # Existing container (e.g. from docker-compose): start it if stopped
        if [ "$($DOCKER inspect -f '{{.State.Running}}' "$NEO4J_CONTAINER")" != "true" ]; then
            echo "Starting existing Neo4j container $NEO4J_CONTAINER..."
            $DOCKER start "$NEO4J_CONTAINER" >/dev/null
        fi
        NETWORK=$($DOCKER inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$NEO4J_CONTAINER" | awk '{print $1}')
        echo "Using Neo4j container $NEO4J_CONTAINER on network $NETWORK"
    else
        echo "Starting Neo4j ($NEO4J_IMAGE) as $NEO4J_CONTAINER on network $NEO4J_NETWORK..."
        $DOCKER network inspect "$NEO4J_NETWORK" &>/dev/null || $DOCKER network create "$NEO4J_NETWORK" >/dev/null
        $DOCKER run -d --name "$NEO4J_CONTAINER" \
            --network "$NEO4J_NETWORK" --network-alias neo4j \
            -p 7474:7474 -p 7687:7687 \
            -e NEO4J_AUTH="$NEO4J_AUTH" \
            -v "$NEO4J_VOLUME:/data" \
            "$NEO4J_IMAGE" >/dev/null
        NETWORK=$NEO4J_NETWORK
    fi

    echo -n "Waiting for Neo4j to accept connections"
    local user=${NEO4J_AUTH%%/*} pass=${NEO4J_AUTH#*/}
    for i in $(seq 1 60); do
        if $DOCKER exec "$NEO4J_CONTAINER" cypher-shell -u "$user" -p "$pass" "RETURN 1" &>/dev/null; then
            echo " -- ready"
            return
        fi
        echo -n "."; sleep 2
    done
    echo ""
    echo "ERROR: Neo4j did not become ready in 2 minutes (docker logs $NEO4J_CONTAINER)"
    exit 1
}


# -----------------------------------------------------------------------
# Steps
# -----------------------------------------------------------------------
step_header() { echo ""; echo "----------------------------------------"; echo "Step: $1"; echo "----------------------------------------"; }

for s in "${STEPS_TO_RUN[@]}"; do
    case "$s" in
        download)
            step_header "1 download"
            if [ -z "$TASK_DOWNLOAD" ]; then
                echo "Skipped: TASK_DOWNLOAD is not set (run --list and set TASK_DOWNLOAD=<name>)."
            else
                run_task "$TASK_DOWNLOAD"
            fi ;;
        convert)
            step_header "2 convert"
            run_task "$TASK_CONVERT" ;;
        stats)
            step_header "2b conversion stats"
            if [ ! -f jsonify/conversion_stats.py ]; then
                echo "Skipped: jsonify/conversion_stats.py not found."
            else
                container /opt/airflow/dags/jsonify/conversion_stats.py \
                    --ini /opt/airflow/dags/jsonify/jsonify.ini \
                    --out-dir /opt/airflow/dags/jsonify/stats \
                    --name "conversion_results_$DS"
            fi ;;
        ontologies)
            step_header "3 ontologies"
            if [ "$ONTOLOGY_SOURCE" == "task" ]; then
                run_task "$TASK_ONTOLOGIES"
            else
                # URLs from NER/bioner.ini; download, unzip, process_ontology.sh
                force=(); [ $FORCE_ONTOLOGIES == 1 ] && force=(--force)
                container /opt/standalone/fetch_ontologies.py \
                    --ini /opt/airflow/dags/NER/bioner.ini "${force[@]}"
            fi ;;
        vocabulary)
            step_header "3b vocabulary"
            run_task "$TASK_VOCABULARY" ;;
        preprocess)
            step_header "4 preprocess"
            run_task "$TASK_PREPROCESS" ;;
        ner)
            step_header "5 ner"
            run_task "$TASK_NER" ;;
        validate)
            step_header "6 validate"
            run_task "$TASK_VALIDATE" ;;
        graph)
            step_header "7 graph"
            if [ -z "$TASK_GRAPH" ]; then
                echo "Skipped: TASK_GRAPH is not set (run --list and set TASK_GRAPH=<name>)."
            else
                ensure_neo4j
                run_task "$TASK_GRAPH"
                echo "Neo4j Browser: http://localhost:7474 (container $NEO4J_CONTAINER keeps running)"
            fi ;;
        export)
            step_header "8 export"
            if [ -z "$TASK_EXPORT" ]; then
                echo "Skipped: TASK_EXPORT is not set."
            else
                ensure_neo4j
                run_task "$TASK_EXPORT"
                echo "Exported files:"
                ls -l database/output/ 2>/dev/null || echo "  (database/output not found -- see the task's log above for where it wrote)"
            fi ;;
    esac
done


# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
echo ""
echo "Done: ${STEPS_TO_RUN[*]}"
[ -n "$LOG_FILE" ] && echo "Log: $LOG_FILE"
exit 0