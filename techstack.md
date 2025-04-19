graph LR
    subgraph User/Client Device
        UI[Frontend App / Device (Sends Audio/Context)]
    end

    subgraph Cloud / Backend Infrastructure
        LB[Load Balancer / API Gateway]

        subgraph Backend Application (FastAPI - Containerized e.g., Docker)
            direction LR
            FAPI[FastAPI App (main.py, routers)]

            subgraph Core Services (services/)
                CS[Conversation Service]
                TS[Transcription Service]
                NLS[NLU Service]
                TTS_S[Synthesis Service]
                NAV[Navigation Service]
                SS[Safety Service]
                TR_S[Translation Service]
                AS[Audio Service (Implicit/Combined)]
            end

            subgraph External Clients (core/clients/)
                GSTT_C[Google STT Client]
                GTTS_C[Google TTS Client]
                GTR_C[Google Translate Client]
                GMAPS_C[Google Maps Client]
                GEM_C[Google Gemini Client]
                OAI_C[OpenAI Client]
                TW_C[Twilio Client]
            end

            subgraph Local Components
                direction TB
                subgraph Audio Libs (Imported)
                  PD_LIB[Pydub Lib / FFmpeg]
                  LR_LIB[Librosa Lib]
                  NR_LIB[NoiseReduce Lib]
                end
                subgraph ML Models (Loaded)
                    YOLO[YOLO Models (.pt)]
                    MP[MediaPipe Models]
                end
            end

            %% Service Dependencies & Flows
            FAPI --> CS
            CS --> TS
            CS --> TR_S
            CS --> NLS
            CS --> NAV
            CS --> SS
            CS --> TTS_S

            TS --> AS
            TS --> GSTT_C
            TS --> OAI_C
            TS --> TR_S # For language detection fallback

            AS --> PD_LIB
            AS --> LR_LIB
            AS --> NR_LIB

            NLS --> GEM_C
            TR_S --> GTR_C
            NAV --> GMAPS_C
            NAV -- Potentially --> FloodDataSource[Web Scrape/API <br>Flood Data Source]
            SS --> TW_C
            SS --> |Drowsiness| YOLO
            SS --> |Drowsiness| MP
            TTS_S --> GTTS_C

        end

        subgraph External Managed Services
            GCP[Google Cloud Platform APIs <br>(STT, TTS, Translate, Maps, Gemini)]
            OpenAI[OpenAI API (Whisper)]
            Twilio[Twilio API (SMS)]
        end

        subgraph Data Stores
            Redis[Redis <br>(Session/Chat History Cache)]
            DB[(Optional DB <br>e.g., PostgreSQL <br>User Profiles, Contacts)]
        end

         subgraph Ops Tools
             CI_CD[CI/CD Pipeline]
             Monitor[Monitoring & Logging]
         end

    end

    %% Client to External Service Mappings
    GSTT_C --> GCP
    GTTS_C --> GCP
    GTR_C --> GCP
    GMAPS_C --> GCP
    GEM_C --> GCP
    OAI_C --> OpenAI
    TW_C --> Twilio

    %% Main Application Flows
    UI -- HTTPS Request (Audio, Form Data) --> LB
    LB -- Forward Request --> FAPI
    FAPI -- Read/Write Session --> Redis
    FAPI -- Read/Write --> DB
    FAPI -- Read Model Files --> YOLO
    FAPI -- Uses Libs --> MP
    FAPI -- Send Logs --> Monitor

    %% Styles (Optional - for clarity)
    style FAPI fill:#f9f,stroke:#333,stroke-width:2px
    style Redis fill:#fcc,stroke:#333,stroke-width:2px
    style DB fill:#fcc,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style External Managed Services fill:#ccf,stroke:#333,stroke-width:2px
    style Local Components fill:#ffc,stroke:#333,stroke-width:1px
    style Ops Tools fill:#eee,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
