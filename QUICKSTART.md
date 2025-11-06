# GitStats JavaFX - Quick Start Guide

## Prerequisites

- **Java Development Kit (JDK) 17 or higher**
  - Download from [Oracle](https://www.oracle.com/java/technologies/downloads/) or use OpenJDK
  - Verify: `java -version` should show version 17+

- **Apache Maven 3.8 or higher**
  - Download from [Maven website](https://maven.apache.org/download.cgi)
  - Verify: `mvn -version`

- **Git**
  - Must be installed and accessible from command line
  - Verify: `git --version`

## Building the Project

1. **Navigate to the project directory:**
   ```bash
   cd gitstats3
   ```

2. **Clean and compile:**
   ```bash
   mvn clean compile
   ```

3. **Run tests (when implemented):**
   ```bash
   mvn test
   ```

4. **Package as executable JAR:**
   ```bash
   mvn clean package
   ```
   This creates `target/gitstats-3.0.0-jar-with-dependencies.jar`

## Running the Application

### Method 1: Using Maven Plugin (Development)
```bash
mvn javafx:run
```

### Method 2: Using the packaged JAR
```bash
java -jar target/gitstats-3.0.0-jar-with-dependencies.jar
```

### Method 3: Direct execution with JavaFX
```bash
java --module-path /path/to/javafx-sdk/lib \
     --add-modules javafx.controls,javafx.fxml \
     -jar target/gitstats-3.0.0-jar-with-dependencies.jar
```

## Using the Application

1. **Select Repository:**
   - Click "Browse..." button
   - Navigate to a Git repository directory
   - Click "Select Folder"

2. **Analyze Repository:**
   - Click "Analyze" button
   - Watch the progress bar for analysis status
   - Wait for completion

3. **View Results:**
   - Click through the tabs to see different statistics:
     - **Summary:** Overall repository metrics
     - **Authors:** Contributor statistics
     - **Files:** File-level analysis
     - **Code Metrics:** Quality indicators

4. **Export Results:**
   - Use **File → Export...** menu
   - Choose format (HTML, PDF, JSON)
   - Save to desired location

## Current Implementation Status

### ✅ Completed Components
- Project structure and Maven configuration
- JavaFX application skeleton
- Main UI with FXML and CSS styling
- Configuration management
- Git command execution wrapper
- Complete data model (7 classes)
- Analysis orchestrator framework

### 🚧 In Progress / Pending
- **CommitAnalyzer implementation** (High Priority)
- **FileAnalyzer implementation** (High Priority)
- **Code metrics calculators** (High Priority)
  - Halstead metrics
  - McCabe complexity
  - Maintainability Index
  - OOP metrics
- **UI controllers for each tab** (Medium Priority)
- **Report generators** (Medium Priority)
  - HTML export
  - PDF export
  - JSON export
- **Unit tests** (Low Priority)

## Troubleshooting

### "Cannot find JavaFX modules"
**Solution:** Ensure JavaFX is included in Maven dependencies or set module-path correctly.

### "Git command not found"
**Solution:** Install Git and ensure it's in your system PATH.

### "Java version mismatch"
**Solution:** Make sure you're using JDK 17+:
```bash
export JAVA_HOME=/path/to/jdk-17
```

### Application won't start
**Solution:** Check logs in `logs/gitstats.log` for detailed error messages.

## Configuration

Configuration file is stored at:
- **Linux/Mac:** `~/.gitstats/config.properties`
- **Windows:** `%USERPROFILE%\.gitstats\config.properties`

Default settings include:
```properties
maxCommitDiff = 100000
maxExtensionLength = 32
maxFilenameLengthInCharts = 40
projectName = (auto-detected)
```

## Development Workflow

1. **Make code changes**
2. **Compile:** `mvn compile`
3. **Test:** `mvn test`
4. **Run:** `mvn javafx:run`
5. **Package:** `mvn package` (for distribution)

## Next Steps for Developers

See `IMPLEMENTATION_GUIDE.md` for detailed implementation roadmap.

### Immediate priorities:
1. Implement `CommitAnalyzer.analyze()` method
2. Implement `FileAnalyzer.analyze()` method
3. Create metrics calculation classes
4. Build out UI controllers for each tab

## Resources

- **JavaFX Documentation:** https://openjfx.io/
- **Maven Documentation:** https://maven.apache.org/guides/
- **Original Python GitStats:** See `../gitstats.py` for reference implementation

## Getting Help

For issues or questions:
1. Check `IMPLEMENTATION_GUIDE.md` for architecture details
2. Review `README.md` for project overview
3. Examine existing code comments and Javadoc
4. Check logs in `logs/` directory

## License

[Include your license information here]
