# GitStats JavaFX - Modular Java Port

A modern, modular Java port of GitStats with JavaFX GUI for analyzing Git repository statistics.

## Features

- **Modular Architecture**: Clean separation of concerns with dedicated packages
- **JavaFX GUI**: Modern, responsive user interface
- **Comprehensive Metrics**: 
  - Code complexity analysis (Halstead, McCabe)
  - OOP metrics (Distance from Main Sequence)
  - Team collaboration metrics
  - Repository health dashboard
- **Interactive Visualizations**: Charts and graphs for all metrics
- **Multi-threading**: Parallel processing for large repositories
- **Export Capabilities**: HTML, PDF, and JSON reports

## Architecture

```
com.gitstats/
├── core/          - Core business logic and configuration
├── model/         - Data models and entities
├── analyzer/      - Repository analysis engines
├── metrics/       - Code metrics calculators
├── ui/            - JavaFX UI components
│   ├── controller/    - FXML controllers
│   └── component/     - Custom UI components
├── report/        - Report generation
└── util/          - Utility classes
```

## Requirements

- Java 17 or higher
- Maven 3.8+
- Git (installed and accessible in PATH)

## Building

```bash
mvn clean install
```

## Running

```bash
mvn javafx:run
```

Or run the JAR:
```bash
java -jar target/gitstats-javafx-3.0.0.jar
```

## Usage

1. Launch the application
2. Select a Git repository
3. Configure analysis options
4. Click "Analyze"
5. View results in the interactive dashboard
6. Export reports as needed

## Modules

### Core Package (`com.gitstats.core`)
- `GitStatsEngine`: Main analysis orchestrator
- `Configuration`: Application configuration management
- `GitCommandExecutor`: Git command execution wrapper

### Model Package (`com.gitstats.model`)
- `RepositoryData`: Repository statistics container
- `AuthorStatistics`: Per-author metrics
- `CommitData`: Individual commit information
- `CodeMetrics`: Code quality metrics

### Analyzer Package (`com.gitstats.analyzer`)
- `RepositoryAnalyzer`: Main repository analyzer
- `CommitAnalyzer`: Commit history analyzer
- `FileAnalyzer`: File-level analysis
- `BranchAnalyzer`: Branch analysis

### Metrics Package (`com.gitstats.metrics`)
- `OOPMetricsAnalyzer`: Object-oriented metrics
- `HalsteadMetrics`: Halstead complexity metrics
- `McCabeMetrics`: Cyclomatic complexity
- `MaintainabilityIndex`: Maintainability calculator

### UI Package (`com.gitstats.ui`)
- JavaFX controllers and custom components
- Interactive charts and visualizations
- Responsive layouts

### Report Package (`com.gitstats.report`)
- `HTMLReportGenerator`: HTML report creation
- `PDFReportGenerator`: PDF export
- `JSONExporter`: JSON data export

## Key Design Patterns

- **MVC Pattern**: Separation of UI, logic, and data
- **Strategy Pattern**: Pluggable analyzers and report generators
- **Observer Pattern**: Real-time progress updates
- **Factory Pattern**: Creating analyzers and reports
- **Singleton Pattern**: Configuration and shared resources

## License

Same as original GitStats project
